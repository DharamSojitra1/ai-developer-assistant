from dotenv import load_dotenv
import os

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "AI Developer Assistant")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
MODEL_NAME = os.getenv("MODEL_NAME")
MOCK_MODE = os.getenv("MOCK_MODE", "true").lower() == "true"
REQUEST_TIMEOUT = int(os.getenv("REQUEST_TIMEOUT", "30"))
FRONTEND_URL = "http://localhost:5173"
API_KEY = os.getenv("API_KEY")
if not API_KEY:
    raise ValueError("API_KEY is missing from environment variables")
APP_ENV = os.getenv("APP_ENV", "development")
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
MONGODB_URI = os.getenv(
    "MONGODB_URI",
    "mongodb://localhost:27017",
)

MONGODB_DATABASE = os.getenv(
    "MONGODB_DATABASE",
    "ai_developer_assistant",
)