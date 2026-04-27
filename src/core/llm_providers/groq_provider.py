from langchain_groq import ChatGroq
from src.core.llm_providers.base import BaseProvider


class GroqProvider(BaseProvider):

    async def create(self, config):
        
        model_name = config["model_name"]
        temperature = config.get("temperature", 0)
        api_key = config.get("api_key")
        
        if not api_key:
            raise ValueError("Groq API key is required")
        
        return ChatGroq(
            model=model_name,
            temperature=temperature,
            api_key=api_key
        )