"""
Configuration Management
========================

Centralized configuration using Pydantic Settings.
Supports YAML config files with environment variable overrides.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


# Project root directory
PROJECT_ROOT = Path(__file__).parent.parent.parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"
PROMPTS_DIR = PROJECT_ROOT / "prompts"
DATA_DIR = PROJECT_ROOT / "data"
LOGS_DIR = PROJECT_ROOT / "logs"


class AppConfig(BaseModel):
    """Application settings."""
    
    name: str = "Memory Janitor"
    version: str = "0.1.0"
    debug: bool = False


class PiecesConfig(BaseModel):
    """Pieces OS connection settings."""
    
    host: str = "http://localhost"
    port: int = 39300
    timeout: int = 30
    checkpoint_file: str = "data/pieces_checkpoint.json"
    
    @property
    def base_url(self) -> str:
        return f"{self.host}:{self.port}"


class Mem0Config(BaseModel):
    """Mem0 connection settings."""
    
    mode: Literal["cloud", "local"] = "cloud"
    api_base: str = "https://api.mem0.ai/v1"
    default_user_id: str = "memory_janitor_user"
    metadata: dict[str, Any] = Field(default_factory=dict)


class GeminiConfig(BaseModel):
    """Gemini LLM settings."""
    
    model: str = "gemini-1.5-flash"
    temperature: float = 0.3
    max_tokens: int = 2048


class AnthropicConfig(BaseModel):
    """Anthropic LLM settings."""
    
    model: str = "claude-3-5-haiku-20241022"
    temperature: float = 0.3
    max_tokens: int = 2048


class LLMConfig(BaseModel):
    """LLM provider settings."""
    
    provider: Literal["gemini", "anthropic"] = "gemini"
    gemini: GeminiConfig = Field(default_factory=GeminiConfig)
    anthropic: AnthropicConfig = Field(default_factory=AnthropicConfig)


class SchedulerConfig(BaseModel):
    """Scheduler settings."""
    
    enabled: bool = True
    interval_minutes: int = 60
    timezone: str = "Asia/Shanghai"


class CleanerConfig(BaseModel):
    """Cleaner node settings."""
    
    prompt_file: str = "prompts/cleaner.txt"


class ReasonerConfig(BaseModel):
    """Reasoner node settings."""
    
    prompt_file: str = "prompts/reasoner.txt"
    high_priority_categories: list[str] = Field(
        default_factory=lambda: [
            "core_decision",
            "tech_discovery",
            "user_preference",
            "project_milestone",
        ]
    )


class DeduplicatorConfig(BaseModel):
    """Deduplicator node settings."""
    
    similarity_threshold: float = 0.85
    search_limit: int = 5


class PipelineConfig(BaseModel):
    """Processing pipeline settings."""
    
    batch_size: int = 10
    cleaner: CleanerConfig = Field(default_factory=CleanerConfig)
    reasoner: ReasonerConfig = Field(default_factory=ReasonerConfig)
    deduplicator: DeduplicatorConfig = Field(default_factory=DeduplicatorConfig)


class DashboardConfig(BaseModel):
    """Dashboard settings."""
    
    host: str = "127.0.0.1"
    port: int = 7860
    share: bool = False


class LoggingConfig(BaseModel):
    """Logging settings."""
    
    level: str = "INFO"
    format: Literal["json", "console"] = "json"
    file: str = "logs/memory_janitor.log"
    max_size_mb: int = 10
    backup_count: int = 5


class Settings(BaseSettings):
    """
    Main settings class.
    
    Loads from YAML config file with environment variable overrides.
    """
    
    model_config = SettingsConfigDict(
        env_prefix="MJ_",
        env_nested_delimiter="__",
        extra="ignore",
    )
    
    # API Keys (from environment)
    mem0_api_key: str = Field(default="", alias="MEM0_API_KEY")
    google_api_key: str = Field(default="", alias="GOOGLE_API_KEY")
    anthropic_api_key: str = Field(default="", alias="ANTHROPIC_API_KEY")
    
    # Nested configs
    app: AppConfig = Field(default_factory=AppConfig)
    pieces: PiecesConfig = Field(default_factory=PiecesConfig)
    mem0: Mem0Config = Field(default_factory=Mem0Config)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    scheduler: SchedulerConfig = Field(default_factory=SchedulerConfig)
    pipeline: PipelineConfig = Field(default_factory=PipelineConfig)
    dashboard: DashboardConfig = Field(default_factory=DashboardConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    @classmethod
    def from_yaml(cls, config_path: Path | None = None) -> "Settings":
        """Load settings from YAML file."""
        if config_path is None:
            config_path = CONFIG_DIR / "settings.yaml"
        
        config_data: dict[str, Any] = {}
        if config_path.exists():
            with open(config_path) as f:
                config_data = yaml.safe_load(f) or {}
        
        return cls(**config_data)


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings.from_yaml()


def load_prompt(prompt_file: str) -> str:
    """Load a prompt template from file."""
    prompt_path = PROJECT_ROOT / prompt_file
    if not prompt_path.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_path}")
    return prompt_path.read_text().strip()
