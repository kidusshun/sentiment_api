import os
from dotenv import load_dotenv
from pydantic import BaseModel

load_dotenv(".env")

class Settings(BaseModel):
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    GEMINI_BASE_URL: str = os.getenv("GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/")
    NEWS_API_KEY: str = os.getenv("NEWS_API_KEY", "")
    FIRE_CRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")


MySettings = Settings()