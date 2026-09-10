from abc import ABC, abstractmethod
from typing import List, Dict, Any, Generator

class BaseProvider(ABC):
    @abstractmethod
    def list_models(self) -> List[Dict[str, Any]]:
        pass
        
    @abstractmethod
    def test_connection(self) -> bool:
        pass
        
    @abstractmethod
    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        pass

    def generate_chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        raise NotImplementedError("Streaming not supported by this provider adapter")
        
    def get_status(self) -> Dict[str, Any]:
        return {"status": "untested"}
        
    def normalize_error(self, e: Exception) -> Exception:
        return e
