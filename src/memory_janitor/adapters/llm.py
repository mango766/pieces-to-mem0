"""
LLM Adapters
============

Implements LLMProvider port for various LLM services.
Supports Gemini and Anthropic with easy switching.
"""

import asyncio
from abc import ABC
from typing import Any

from memory_janitor.config import get_settings
from memory_janitor.domain.ports import LLMProvider
from memory_janitor.logging import get_logger

logger = get_logger(__name__)


class BaseLLMAdapter(LLMProvider, ABC):
    """Base class for LLM adapters with common functionality."""
    
    async def batch_generate(
        self,
        prompts: list[str],
        system_prompt: str | None = None,
        temperature: float = 0.3,
    ) -> list[str]:
        """Default batch implementation using concurrent single calls."""
        tasks = [
            self.generate(prompt, system_prompt, temperature)
            for prompt in prompts
        ]
        return await asyncio.gather(*tasks)


class GeminiAdapter(BaseLLMAdapter):
    """Adapter for Google Gemini API."""
    
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.google_api_key
        self.model = settings.llm.gemini.model
        self.default_temperature = settings.llm.gemini.temperature
        self.default_max_tokens = settings.llm.gemini.max_tokens
        
        self._client: Any = None
    
    def _get_client(self) -> Any:
        """Lazy initialize the Gemini client."""
        if self._client is None:
            try:
                from langchain_google_genai import ChatGoogleGenerativeAI
                
                self._client = ChatGoogleGenerativeAI(
                    model=self.model,
                    google_api_key=self.api_key,
                    temperature=self.default_temperature,
                    max_output_tokens=self.default_max_tokens,
                )
            except ImportError:
                raise ImportError("langchain-google-genai is required for Gemini support")
        return self._client
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text using Gemini."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            client = self._get_client()
            
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            
            response = await client.ainvoke(messages)
            
            return response.content if hasattr(response, "content") else str(response)
            
        except Exception as e:
            logger.error("gemini_generate_failed", error=str(e))
            raise
    
    async def health_check(self) -> bool:
        """Check if Gemini API is available."""
        try:
            await self.generate("Hello", max_tokens=10)
            return True
        except Exception:
            return False


class AnthropicAdapter(BaseLLMAdapter):
    """Adapter for Anthropic Claude API."""
    
    def __init__(self) -> None:
        settings = get_settings()
        self.api_key = settings.anthropic_api_key
        self.model = settings.llm.anthropic.model
        self.default_temperature = settings.llm.anthropic.temperature
        self.default_max_tokens = settings.llm.anthropic.max_tokens
        
        self._client: Any = None
    
    def _get_client(self) -> Any:
        """Lazy initialize the Anthropic client."""
        if self._client is None:
            try:
                from langchain_anthropic import ChatAnthropic
                
                self._client = ChatAnthropic(
                    model=self.model,
                    anthropic_api_key=self.api_key,
                    temperature=self.default_temperature,
                    max_tokens=self.default_max_tokens,
                )
            except ImportError:
                raise ImportError("langchain-anthropic is required for Anthropic support")
        return self._client
    
    async def generate(
        self,
        prompt: str,
        system_prompt: str | None = None,
        temperature: float = 0.3,
        max_tokens: int = 2048,
    ) -> str:
        """Generate text using Claude."""
        try:
            from langchain_core.messages import HumanMessage, SystemMessage
            
            client = self._get_client()
            
            messages = []
            if system_prompt:
                messages.append(SystemMessage(content=system_prompt))
            messages.append(HumanMessage(content=prompt))
            
            response = await client.ainvoke(messages)
            
            return response.content if hasattr(response, "content") else str(response)
            
        except Exception as e:
            logger.error("anthropic_generate_failed", error=str(e))
            raise
    
    async def health_check(self) -> bool:
        """Check if Anthropic API is available."""
        try:
            await self.generate("Hello", max_tokens=10)
            return True
        except Exception:
            return False


def get_llm_adapter() -> LLMProvider:
    """
    Factory function to get the configured LLM adapter.
    
    Returns the adapter based on settings.llm.provider.
    """
    settings = get_settings()
    provider = settings.llm.provider
    
    if provider == "gemini":
        return GeminiAdapter()
    elif provider == "anthropic":
        return AnthropicAdapter()
    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
