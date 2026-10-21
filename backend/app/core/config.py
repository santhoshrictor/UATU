import os
from typing import List
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    PROJECT_NAME: str = "UATU AI Operations Platform"
    STAGE: str = "Stage 1 - Foundation Only"
    ENVIRONMENT: str = "development"
    DEBUG: bool = False
    
    API_V1_STR: str = "/api/v1"
    
    # Server Binding
    HOST: str = "127.0.0.1"
    PORT: int = 8000
    
    # Strictly configured development CORS origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]
    
    # PostgreSQL Configuration
    POSTGRES_SERVER: str = Field(default="127.0.0.1")
    POSTGRES_PORT: int = Field(default=5432)
    POSTGRES_USER: str = Field(default="postgres")
    POSTGRES_PASSWORD: str = Field(default="")
    POSTGRES_DB: str = Field(default="workplace_dev")
    TEST_POSTGRES_DB: str = Field(default="workplace_test")
    
    # Bounded Database Timeout (seconds)
    DB_CONNECT_TIMEOUT_SECONDS: float = Field(default=2.0)
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    @property
    def database_url(self) -> str:
        """Returns standard PostgreSQL connection string without exposing in repr."""
        auth = self.POSTGRES_USER
        if self.POSTGRES_PASSWORD:
            auth += f":{self.POSTGRES_PASSWORD}"
        return f"postgresql+psycopg://{auth}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"

    @property
    def test_database_url(self) -> str:
        """Returns isolated test PostgreSQL connection string."""
        auth = self.POSTGRES_USER
        if self.POSTGRES_PASSWORD:
            auth += f":{self.POSTGRES_PASSWORD}"
        return f"postgresql+psycopg://{auth}@{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.TEST_POSTGRES_DB}"


settings = Settings()
