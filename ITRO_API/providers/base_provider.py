from abc import ABC, abstractmethod

class BaseProvider(ABC):

    @abstractmethod
    def check_api_key(self):
        pass

    @abstractmethod
    def call(self, prompt, max_tokens=1024):
        pass

    @property
    @abstractmethod
    def name(self):
        pass