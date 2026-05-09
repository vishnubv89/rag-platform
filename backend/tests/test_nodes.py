"""
Unit tests for agent/nodes.py

Covers the two pure-Python helpers that contain non-trivial logic:
  - _parse_indices  (LLM response parser for the grader)
  - _CHITCHAT_RE    (intent classifier regex)

No DB, no LLM, no network — fast and deterministic.
"""
import pytest
from rag_chatbot.agent.nodes import _parse_indices, _CHITCHAT_RE


# ---------------------------------------------------------------------------
# _parse_indices
# ---------------------------------------------------------------------------

class TestParseIndices:
    """Grader extracts relevant doc indices from the LLM response text."""

    # --- happy path: valid JSON array -----------------------------------------

    def test_single_index(self):
        assert _parse_indices("[0]", n_docs=3) == [0]

    def test_multiple_indices(self):
        assert _parse_indices("[0, 2]", n_docs=3) == [0, 2]

    def test_empty_array(self):
        assert _parse_indices("[]", n_docs=5) == []

    def test_array_with_spaces(self):
        assert _parse_indices("[ 1 , 2 ]", n_docs=5) == [1, 2]

    def test_array_embedded_in_prose(self):
        # LLM sometimes wraps its answer in prose
        result = _parse_indices("Relevant chunks are [0, 1].", n_docs=4)
        assert result == [0, 1]

    # --- out-of-range filtering -----------------------------------------------

    def test_out_of_range_indices_filtered(self):
        # n_docs=3 means valid indices are 0,1,2 only
        result = _parse_indices("[0, 5]", n_docs=3)
        assert result == [0]

    def test_all_out_of_range_returns_empty(self):
        result = _parse_indices("[10, 20]", n_docs=3)
        assert result == []

    def test_zero_n_docs_always_empty(self):
        result = _parse_indices("[0]", n_docs=0)
        assert result == []

    # --- fallback: bare integer extraction ------------------------------------

    def test_fallback_extracts_integer_from_prose(self):
        # "[" not present; should fall back to extracting bare integers
        result = _parse_indices("chunk 1 seems relevant", n_docs=5)
        assert 1 in result

    def test_fallback_deduplicates_integers(self):
        result = _parse_indices("1 and 1 and 1", n_docs=5)
        assert result.count(1) == 1

    def test_fallback_out_of_range_filtered(self):
        result = _parse_indices("chunk 9 is relevant", n_docs=3)
        assert result == []

    # --- edge cases -----------------------------------------------------------

    def test_empty_string(self):
        assert _parse_indices("", n_docs=5) == []

    def test_whitespace_only(self):
        assert _parse_indices("   ", n_docs=5) == []

    def test_order_preserved_in_array(self):
        # indices should stay in the order the LLM listed them
        result = _parse_indices("[2, 0, 1]", n_docs=5)
        assert result == [2, 0, 1]

    def test_malformed_json_falls_back_to_integers(self):
        # Brackets present but JSON is invalid — should still extract what it can
        result = _parse_indices("[0, abc, 2]", n_docs=5)
        # fallback extracts 0 and 2 from bare digit scan
        assert 0 in result
        assert 2 in result


# ---------------------------------------------------------------------------
# _CHITCHAT_RE — intent classifier
# ---------------------------------------------------------------------------

class TestChitchatRegex:
    """The regex should catch social greetings and deflect them away from RAG."""

    # --- should match (chitchat / social) -------------------------------------

    @pytest.mark.parametrize("phrase", [
        "hi",
        "Hi!",
        "hello",
        "hey",
        "Hey!",
        "howdy",
        "greetings",
        "good morning",
        "good afternoon",
        "good evening",
        "good day",
        "what's up",
        "whats up",
        "sup",
        "yo",
        "hiya",
        "how are you",
        "how are you?",
        "how do you do",
        "nice to meet you",
        "thanks",
        "thank you",
        "thanks you",
        "bye",
        "goodbye",
        "see you",
        "take care",
        "who are you",
        "what are you",
        "what can you do",
        "  hi  ",            # leading/trailing whitespace
        "Hello!",
        "Hi!!",
    ])
    def test_matches_chitchat(self, phrase):
        assert _CHITCHAT_RE.match(phrase.strip()), f"Expected match for: {phrase!r}"

    # --- should NOT match (knowledge questions) --------------------------------

    @pytest.mark.parametrize("phrase", [
        "What is the capital of France?",
        "Explain quantum computing",
        "How do I reset my password?",
        "Tell me about the company return policy",
        "What are the system requirements?",
        "hello world this is a question",   # starts with hello but has content
        "Hello there!",                     # word after hello — not pure greeting
        "byebye",                           # bye+ matches bye/byee, not repeated "bye"
        "thanks for the explanation, now what is X?",
        "How does the billing work?",
        "Can you show me the onboarding steps?",
        "What did Einstein discover?",
    ])
    def test_does_not_match_knowledge_questions(self, phrase):
        assert not _CHITCHAT_RE.match(phrase.strip()), f"Unexpected match for: {phrase!r}"
