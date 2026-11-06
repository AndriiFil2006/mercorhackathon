from functools import lru_cache
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "sqlite:///./legal_eval.db"
    ai_provider: Literal["mock", "gemini", "openai"] = "mock"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = Field(default="gemini-2.5-flash", min_length=1, max_length=200)
    gemini_timeout_seconds: float = Field(default=45, gt=0, le=300)
    gemini_max_retries: int = Field(default=2, ge=0, le=5)
    gemini_max_output_tokens: int = Field(default=2048, ge=256, le=8192)
    ai_prompt_version: str = Field(default="legal-v1", min_length=1, max_length=50)
    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = "gpt-4o-mini"
    cors_origins: str = "http://localhost:3000,http://localhost:5173"
@lru_cache
def get_settings() -> Settings:
    return Settings()

