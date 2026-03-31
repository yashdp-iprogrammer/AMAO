# from abc import ABC, abstractmethod


# class BaseAgent(ABC):

#     def __init__(self, name, config):
#         self.name = name
#         self.config = config

#     @abstractmethod
#     def run(self, state: dict):
#         pass


from abc import ABC, abstractmethod

class BaseAgent(ABC):

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    async def run(self, state: dict) -> dict:
        pass