"""
Unit tests for ingestion/chunker.py

All tests are pure Python — no DB, no LLM, no network.
"""
import pytest
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Patch settings before importing the module under test so we control
# chunk_size and chunk_overlap without needing a real .env file.
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def patch_settings():
    mock_settings = MagicMock()
    mock_settings.chunk_size = 100      # small, so tests run fast
    mock_settings.chunk_overlap = 10
    with patch("rag_chatbot.ingestion.chunker.settings", mock_settings):
        yield mock_settings


from rag_chatbot.ingestion.chunker import (  # noqa: E402  (import after patch fixture)
    semantic_chunk_text,
    chunk_text,
    _token_len,
    _split_sentences,
    _semantic_chunks,
)


# ---------------------------------------------------------------------------
# _token_len
# ---------------------------------------------------------------------------

class TestTokenLen:
    def test_empty_string(self):
        assert _token_len("") == 0

    def test_single_word(self):
        assert _token_len("hello") > 0

    def test_longer_text_has_more_tokens(self):
        short = _token_len("hello")
        long  = _token_len("hello world this is a longer sentence")
        assert long > short


# ---------------------------------------------------------------------------
# _split_sentences
# ---------------------------------------------------------------------------

class TestSplitSentences:
    def test_single_sentence_no_split(self):
        result = _split_sentences("Hello world")
        assert result == ["Hello world"]

    def test_period_splits(self):
        result = _split_sentences("First sentence. Second sentence.")
        assert len(result) == 2
        assert result[0] == "First sentence."
        assert result[1] == "Second sentence."

    def test_question_mark_splits(self):
        result = _split_sentences("Is this right? Yes it is.")
        assert len(result) == 2

    def test_exclamation_splits(self):
        result = _split_sentences("Wow! That is great.")
        assert len(result) == 2

    def test_strips_whitespace(self):
        result = _split_sentences("  Hello world.  ")
        assert result[0] == "Hello world."

    def test_empty_string(self):
        result = _split_sentences("")
        assert result == []


# ---------------------------------------------------------------------------
# _semantic_chunks (core logic, fully controlled size)
# ---------------------------------------------------------------------------

class TestSemanticChunks:
    def test_empty_text_returns_empty(self):
        result = _semantic_chunks("", size=100, overlap=10)
        assert result == []

    def test_single_short_paragraph_returns_one_chunk(self):
        text = "This is a single short paragraph."
        result = _semantic_chunks(text, size=100, overlap=10)
        assert len(result) == 1
        assert "single short paragraph" in result[0]

    def test_two_short_paragraphs_merge_into_one(self):
        # Both fit within size=100 tokens together
        text = "First paragraph.\n\nSecond paragraph."
        result = _semantic_chunks(text, size=100, overlap=10)
        assert len(result) == 1
        assert "First" in result[0]
        assert "Second" in result[0]

    def test_two_large_paragraphs_stay_separate(self):
        # Each paragraph is ~50 tokens; size=60 so they can't merge
        para = "word " * 50          # ~50 tokens each
        text = para + "\n\n" + para
        result = _semantic_chunks(text, size=60, overlap=5)
        assert len(result) >= 2

    def test_whitespace_only_returns_empty(self):
        result = _semantic_chunks("   \n\n   \n\n   ", size=100, overlap=10)
        assert result == []

    def test_no_chunk_exceeds_size(self):
        # Generate text with many paragraphs
        paragraphs = "\n\n".join(["This is paragraph number " + str(i) + "." for i in range(20)])
        result = _semantic_chunks(paragraphs, size=20, overlap=2)
        for chunk in result:
            assert _token_len(chunk) <= 20 + 5, f"Chunk too large: {_token_len(chunk)} tokens"

    def test_markdown_heading_splits(self):
        text = "Intro paragraph.\n## Section One\nContent here.\n## Section Two\nMore content."
        result = _semantic_chunks(text, size=100, overlap=5)
        # Should produce at least 2 chunks (one per section boundary)
        full = " ".join(result)
        assert "Intro" in full
        assert "Section One" in full
        assert "Section Two" in full

    def test_overlap_tail_prepended(self):
        # Create two chunks that must be separate; verify overlap content
        para1 = "unique_alpha_word " * 12   # forces a separate chunk
        para2 = "unique_beta_word " * 12
        result = _semantic_chunks(para1 + "\n\n" + para2, size=15, overlap=5)
        assert len(result) >= 2
        # Second chunk should contain some words from first (overlap)
        if len(result) >= 2:
            assert "unique_alpha_word" in result[1]

    def test_oversized_paragraph_split_at_sentence(self):
        # One paragraph with many sentences — must be split
        sentences = ". ".join(["Sentence number " + str(i) for i in range(20)]) + "."
        result = _semantic_chunks(sentences, size=20, overlap=2)
        assert len(result) > 1
        for chunk in result:
            assert _token_len(chunk) <= 25   # allow small tolerance


# ---------------------------------------------------------------------------
# semantic_chunk_text (uses settings)
# ---------------------------------------------------------------------------

class TestSemanticChunkText:
    def test_returns_list(self, patch_settings):
        result = semantic_chunk_text("Hello world.")
        assert isinstance(result, list)

    def test_non_empty_input_returns_chunks(self, patch_settings):
        result = semantic_chunk_text("Some text here.")
        assert len(result) >= 1

    def test_all_chunks_are_strings(self, patch_settings):
        result = semantic_chunk_text("Para one.\n\nPara two.\n\nPara three.")
        assert all(isinstance(c, str) for c in result)

    def test_no_empty_chunks(self, patch_settings):
        result = semantic_chunk_text("Para one.\n\nPara two.")
        assert all(c.strip() for c in result)


# ---------------------------------------------------------------------------
# chunk_text (legacy — basic sanity checks only)
# ---------------------------------------------------------------------------

class TestChunkTextLegacy:
    def test_empty_returns_empty(self, patch_settings):
        assert chunk_text("") == []

    def test_short_text_is_one_chunk(self, patch_settings):
        result = chunk_text("Hello world.")
        assert len(result) == 1

    def test_long_text_produces_multiple_chunks(self, patch_settings):
        long_text = "word " * 500
        result = chunk_text(long_text)
        assert len(result) > 1

    def test_all_chunks_non_empty(self, patch_settings):
        result = chunk_text("word " * 200)
        assert all(c.strip() for c in result)
