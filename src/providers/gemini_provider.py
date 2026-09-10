import requests
from typing import List, Dict, Any
from src.providers.base_provider import BaseProvider
from src.providers.litellm_router import classify_litellm_error
import litellm

class GeminiProvider(BaseProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def list_models(self) -> List[Dict[str, Any]]:
        if not self.api_key: return []
        try:
            res = requests.get(f"https://generativelanguage.googleapis.com/v1beta/models?key={self.api_key}", timeout=10)
            if res.status_code != 200:
                raise Exception(f"Gemini API Hatası: {res.text}")
                
            data = res.json().get("models", [])
            chat_models = []
            for m in data:
                m_id = m.get("name", "").replace("models/", "")
                if "generateContent" in m.get("supportedGenerationMethods", []):
                    chat_models.append({
                        "id": m_id,
                        "name": m.get("displayName", m_id),
                        "provider": "gemini",
                        "task": "chat-completion",
                        "isCached": False,
                        "isLoaded": False,
                        "isReady": True,
                        "device": "cloud",
                        "status": "ready"
                    })
            return sorted(chat_models, key=lambda x: x["id"], reverse=True)
        except Exception as e:
            raise self.normalize_error(e)
            
    def test_connection(self) -> bool:
        models = self.list_models()
        if not models:
            raise Exception("Gemini hesabında kullanılabilir sohbet modeli bulunamadı.")
        return True
            
    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        raise NotImplementedError("Use generate_chat_stream")
        
    def generate_chat_stream(self, messages: List[Dict[str, str]], **kwargs):
        model_name = kwargs.get("model", "gemini-1.5-flash")
        old_key = litellm.api_key
        litellm.api_key = self.api_key
        
        try:
            response = litellm.completion(
                model=f"gemini/{model_name}" if not model_name.startswith("gemini/") else model_name,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                temperature=kwargs.get("temperature", 0.3),
                max_tokens=kwargs.get("max_tokens", 160)
            )
            
            for chunk in response:
                content = chunk.choices[0].delta.content if chunk.choices else ""
                usage = getattr(chunk, "usage", None)
                if usage:
                    yield {
                        "is_metadata": True,
                        "provider": "Gemini",
                        "model": model_name,
                        "location": "Bulut (Cloud)",
                        "prompt_tokens": getattr(usage, "prompt_tokens", 0),
                        "completion_tokens": getattr(usage, "completion_tokens", 0),
                        "cost": 0.0,
                    }
                elif content:
                    yield {"content": content}
        except Exception as e:
            raise self.normalize_error(e)
        finally:
            litellm.api_key = old_key

    def normalize_error(self, e: Exception) -> Exception:
        return classify_litellm_error(e)
