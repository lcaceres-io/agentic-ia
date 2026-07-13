import os

from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")

if not GEMINI_API_KEY:
    raise RuntimeError(
        "Falta GEMINI_API_KEY. Copia .env.example a .env y completa tu API key "
        "gratuita de https://aistudio.google.com/apikey"
    )
