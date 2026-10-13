import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.1-flash-lite")

# Modelos a probar, en orden de prioridad inicial, separados por coma.
# GEMINI_MODEL (si esta definido) siempre va primero.
_MODELOS_DEFAULT = "gemini-3.1-flash-lite,gemini-3.8-flash,gemini-3.7-flash,gemini-3.5-flash,gemini-3.5-flash-lite,gemini-3-flash-preview,gemini-flash-latest,gemini-flash-lite-latest"
GEMINI_MODELS = list(dict.fromkeys(
    [GEMINI_MODEL]
    + [m.strip() for m in os.getenv("GEMINI_MODELS", _MODELOS_DEFAULT).split(",") if m.strip()]
))

if not GEMINI_API_KEY:
    raise RuntimeError(
        "Falta GEMINI_API_KEY. Copia .env.example a .env y completa tu API key "
        "gratuita de https://aistudio.google.com/apikey"
    )
