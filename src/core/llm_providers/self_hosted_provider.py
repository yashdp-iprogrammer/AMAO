from langchain_openai import ChatOpenAI
from src.core.llm_providers.base import BaseProvider


class SelfHostedProvider(BaseProvider):

    def __init__(self, runtime_manager):
        self.runtime_manager = runtime_manager

    async def create(self, config):
        
        model_name = config["model_name"]        
        base_url = await self.runtime_manager.ensure(config["model_name"])

        return ChatOpenAI(
            model=model_name,
            base_url=base_url,
            api_key="EMPTY",
            temperature=config.get("temperature", 0)
        )