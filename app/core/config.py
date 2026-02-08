from pydantic_settings import BaseSettings
from typing import Optional


class Settings(BaseSettings):
    PROJECT_NAME: str = "VanTrack API"
    VERSION: str = "1.0.0"
    API_V1_STR: str = "/api/v1"
    
    # Database - can use DATABASE_URL directly (Render style) or individual vars
    DATABASE_URL_ENV: Optional[str] = None  # Direct DATABASE_URL from environment
    POSTGRES_SERVER: str = "localhost"
    POSTGRES_PORT: str = "5432"
    POSTGRES_USER: str = "vantrack"
    POSTGRES_PASSWORD: str = "vantrack_secret"
    POSTGRES_DB: str = "vantrack-backend"
    
    @property
    def DATABASE_URL(self) -> str:
        if self.DATABASE_URL_ENV:
            # Convert postgres:// to postgresql+asyncpg:// for async driver
            url = self.DATABASE_URL_ENV
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql+asyncpg://", 1)
            elif url.startswith("postgresql://"):
                url = url.replace("postgresql://", "postgresql+asyncpg://", 1)
            return url
        return f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    @property
    def DATABASE_URL_SYNC(self) -> str:
        if self.DATABASE_URL_ENV:
            # Use sync driver
            url = self.DATABASE_URL_ENV
            if url.startswith("postgres://"):
                url = url.replace("postgres://", "postgresql://", 1)
            return url
        return f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    
    # JWT
    SECRET_KEY: str = "your-secret-key-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24 * 7  # 7 days
    
    # Gemini AI
    GEMINI_API_KEY: Optional[str] = None
    
    class Config:
        env_file = ".env"
        case_sensitive = True


settings = Settings()
