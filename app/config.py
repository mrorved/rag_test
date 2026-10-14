from pydantic_settings import BaseSettings
from pydantic import Field
from typing import Optional
import os

class Settings(BaseSettings):
    LLM_PROVIDER: str = Field(default="openrouter", description="openrouter or nvidia")
    
    OPENROUTER_API_KEY: Optional[str] = Field(default="")
    OPENROUTER_BASE_URL: str = Field(default="https://openrouter.ai/api/v1")
    OPENROUTER_MODEL: str = Field(default="qwen/qwen-2.5-72b-instruct")
    
    NVIDIA_API_KEY: Optional[str] = Field(default="")
    NVIDIA_BASE_URL: str = Field(default="https://integrate.api.nvidia.com/v1")
    NVIDIA_MODEL: str = Field(default="meta/llama-3.3-70b-instruct")
    
    GIGACHAT_CREDENTIALS: Optional[str] = Field(default="", description="Авторизационные данные из личного кабинета GigaChat")
    GIGACHAT_SCOPE: str = Field(default="GIGACHAT_API_PERS", description="GIGACHAT_API_PERS для физлиц, GIGACHAT_API_CORP для юрлиц")
    GIGACHAT_MODEL: str = Field(default="GigaChat-2", description="GigaChat-2 или GigaChat-2-Pro")
    
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    HTTP_PROXY: Optional[str] = Field(default=None, description="Опциональный прокси, e.g. http://127.0.0.1:10808")
    
    # Настройки авторизации для стенда и тестирования
    AUTH_ENABLED: bool = Field(default=True, description="Требовать ли авторизацию для чата и демо")
    AUTH_USERNAME: str = Field(default="admin", description="Логин для доступа")
    AUTH_PASSWORD: str = Field(default="cvgaudio2026", description="Пароль для доступа")
    AUTH_SECRET_TOKEN: str = Field(default="cvg_secret_demo_token_2026", description="Токен для сессии")
    
    DATA_PATH: str = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data", "knowledge_base.json")
    
    @property
    def resolved_provider(self) -> str:
        prov = (self.LLM_PROVIDER or "").strip().lower()
        if prov in ("gigachat", "giga", "sber"):
            return "gigachat"
        # Автоматическое определение, если указан ключ от GigaChat
        if self.GIGACHAT_CREDENTIALS and not self.OPENROUTER_API_KEY and not self.NVIDIA_API_KEY:
            return "gigachat"
        if prov == "openrouter" and not self.OPENROUTER_API_KEY and self.NVIDIA_API_KEY:
            return "nvidia"
        if prov == "nvidia" and not self.NVIDIA_API_KEY and self.OPENROUTER_API_KEY:
            return "openrouter"
        return prov

    @property
    def active_api_key(self) -> str:
        if self.resolved_provider == "gigachat":
            return (self.GIGACHAT_CREDENTIALS or "").strip()
        if self.resolved_provider == "nvidia":
            return (self.NVIDIA_API_KEY or "").strip()
        return (self.OPENROUTER_API_KEY or "").strip()

    @property
    def active_base_url(self) -> str:
        if self.resolved_provider == "nvidia":
            return self.NVIDIA_BASE_URL.strip()
        return self.OPENROUTER_BASE_URL.strip()

    @property
    def active_model(self) -> str:
        if self.resolved_provider == "gigachat":
            return self.GIGACHAT_MODEL.strip()
        if self.resolved_provider == "nvidia":
            return self.NVIDIA_MODEL.strip()
        return self.OPENROUTER_MODEL.strip()

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
