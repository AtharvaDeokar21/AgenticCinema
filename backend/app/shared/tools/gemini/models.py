from enum import Enum


class GeminiProvider(str, Enum):
    GEMINI_API = "gemini_api"
    VERTEX_AI = "vertex_ai"