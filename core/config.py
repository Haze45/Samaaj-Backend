from pydantic_settings import BaseSettings
from pathlib import Path


class Settings(BaseSettings):
    APP_NAME: str = "SamaajBot API"
    SECRET_KEY: str = "change-this-to-a-long-random-secret-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days

    DATABASE_URL: str = "sqlite:///./samaajbot.db"
    UPLOAD_DIR: str = "./uploads"
    CHROMA_DIR: str = "./chroma_db"

    GEMINI_API_KEY: str = ""

    class Config:
        env_file = ".env"


settings = Settings()

Path(settings.UPLOAD_DIR).mkdir(parents=True, exist_ok=True)
Path(settings.CHROMA_DIR).mkdir(parents=True, exist_ok=True)
