from langchain_google_genai import ChatGoogleGenerativeAI
from src.core.llm_providers.base import BaseProvider


class GoogleProvider(BaseProvider):

    async def create(self, config: dict):

        model_name = config["model_name"]
        temperature = config.get("temperature", 0)
        api_key = config.get("api_key")

        if not api_key:
            raise ValueError("Google API key is required")

        llm = ChatGoogleGenerativeAI(
            model=model_name,
            temperature=temperature,
            google_api_key=api_key
        )

        return llm