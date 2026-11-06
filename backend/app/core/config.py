from functools import lru_cache
from pathlib import Path
from typing import Literal
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict
class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=Path(__file__).resolve().parents[2] / ".env", extra="ignore")
    database_url: str = "sqlite:///./legal_eval.db"
    ai_provider: Literal["mock", "gemini", "openai"] = "mock"
    gemini_api_key: str = Field(default="", repr=False)
    gemini_model: str = Field(default="gemini-3.1-flash-lite", min_length=1, max_length=200)
    gemini_timeout_seconds: float = Field(default=45, gt=0, le=300)
    gemini_max_retries: int = Field(default=2, ge=0, le=5)
    gemini_max_output_tokens: int = Field(default=2048, ge=256, le=8192)
    ai_prompt_version: str = Field(default="legal-v1", min_length=1, max_length=50)
    openai_api_key: str = Field(default="", repr=False)
    openai_model: str = "gpt-4o-mini"
    review_mode: Literal["mock", "live"] = "mock"
    groq_api_key: str = Field(default="", repr=False)
    tavily_api_key: str = Field(default="", repr=False)
    review_model_authority: str = "openai/gpt-oss-120b"
    review_model_jurisdiction: str = "openai/gpt-oss-20b"
    review_model_reasoning: str = "qwen/qwen3.8-27b"
    groq_min_interval_seconds: float = Field(default=60, ge=0, le=120)
    reviewer_timeout_seconds: float = Field(default=90, gt=0, le=180)
    reviewer_max_output_tokens: int = Field(default=4000, ge=1500, le=12000)
    review_search_queries: int = Field(default=1, ge=1, le=2)
    review_sources_per_query: int = Field(default=2, ge=1, le=5)
    review_source_chars: int = Field(default=3000, ge=1000, le=20000)
    review_cache_seconds: int = Field(default=3600, ge=0, le=86400)
    chat_context_max_chars: int = Field(default=180000, ge=10000, le=500000)
    cors_origins: str = "http://localhost:8080,http://127.0.0.1:8080,http://localhost:5173"
@lru_cache
def get_settings() -> Settings:
    return Settings()

