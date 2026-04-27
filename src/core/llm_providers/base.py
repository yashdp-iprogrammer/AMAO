class BaseProvider:
    async def create(self, llm_config: dict):
        raise NotImplementedError