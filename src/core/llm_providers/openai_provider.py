from langchain_openai import ChatOpenAI
from src.core.llm_providers.base import BaseProvider


class OpenAIProvider(BaseProvider):

    async def create(self, config):
        
        model_name = config["model_name"]
        temperature = config.get("temperature", 0)
        api_key = config.get("api_key")

        if not api_key:
            raise ValueError("OpenAI API key is required")

        return ChatOpenAI(
            model=model_name,
            temperature=temperature,
            api_key=api_key
        )