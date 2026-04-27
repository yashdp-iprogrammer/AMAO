from src.core.llm_providers.openai_provider import OpenAIProvider
from src.core.llm_providers.groq_provider import GroqProvider
from src.core.llm_providers.google_provider import GoogleProvider
from src.core.llm_providers.self_hosted_provider import SelfHostedProvider


def get_providers(runtime_manager):
    return {
        "openai": OpenAIProvider(),
        "groq": GroqProvider(),
        "google": GoogleProvider(),
        "self_hosted": SelfHostedProvider(runtime_manager),
    }