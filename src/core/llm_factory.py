import os
from langchain_openai import ChatOpenAI
from langchain_groq import ChatGroq
from src.utils.logger import logger


class LLMFactory:

    _cache = {}

    @classmethod
    def create(cls, llm_config: dict):

        model_name = llm_config["model_name"]
        temperature = llm_config.get("temperature", 0)
        api_key = llm_config.get("api_key")

        if not api_key:
            api_key = os.getenv("LLM_API_KEY")

        cache_key = (model_name, temperature, api_key)

        if cache_key in cls._cache:
            logger.info(f"[LLM FACTORY] LLM cache hit | model={model_name}, temperature={temperature}")
            return cls._cache[cache_key]

        logger.info(f"[LLM FACTORY] Initializing LLM | model={model_name}, temperature={temperature}")

        if model_name.lower().startswith("gpt"):
            llm = ChatOpenAI(
                model=model_name,
                temperature=temperature,
                api_key=api_key
            )

        elif "llama" in model_name.lower():
            llm = ChatGroq(
                model=model_name,
                temperature=temperature,
                api_key=api_key
            )

        else:
            logger.warning(f"[LLM FACTORY] Unsupported LLM model: {model_name}")
            raise ValueError(f"Unsupported model: {model_name}")

        cls._cache[cache_key] = llm

        logger.info(f"[LLM FACTORY] LLM initialized and cached | model={model_name}")

        return llm