"""
Pytest configuration for the unit-test suite.

Sets required environment variables before any module-level code runs so
that pydantic-settings' Settings() construction succeeds without a real
.env file or live credentials.  These dummy values are overridden by the
autouse fixtures in individual test modules where needed.
"""
import os

# Set required fields before any rag_chatbot module is imported
os.environ.setdefault("GEMINI_API_KEY", "test-gemini-key")
os.environ.setdefault("DATABASE_URL", "postgresql://test:test@localhost/test")
