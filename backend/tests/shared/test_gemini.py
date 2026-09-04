from app.shared.tools.gemini import GeminiClient


def test_gemini_client_import():
    assert GeminiClient is not None