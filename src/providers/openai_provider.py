import requests
from typing import List, Dict, Any
from src.providers.base_provider import BaseProvider
from src.providers.litellm_router import classify_litellm_error
import litellm

class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        
    def list_models(self) -> List[Dict[str, Any]]:
        if not self.api_key: return []
        try:
            res = requests.get("https://api.openai.com/v1/models", headers={"Authorization": f"Bearer {self.api_key}"}, timeout=10)
            if res.status_code != 200:
                if res.status_code == 401:
                    raise Exception("Geçersiz API Anahtarı")
                elif res.status_code == 429:
                    raise Exception("API kredisi gerekli")
                return []
                
            data = res.json().get("data", [])
            chat_models = []
            for m in data:
                m_id = m.get("id", "")
                non_chat_markers = (
                    "audio", "image", "realtime", "search", "transcribe",
                    "tts", "embedding", "moderation", "whisper", "dall-e",
                )
                is_chat_family = m_id.startswith(("gpt-", "o1", "o3", "o4"))
                if is_chat_family and not any(marker in m_id for marker in non_chat_markers):
                    chat_models.append({
                        "id": m_id,
                        "name": m_id,
                        "provider": "openai",
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
            raise Exception("OpenAI hesabında kullanılabilir sohbet modeli bulunamadı.")
        return True
            
    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        raise NotImplementedError("Use generate_chat_stream")
        
    def generate_chat_stream(self, messages: List[Dict[str, str]], **kwargs):
        model_name = kwargs.get("model", "gpt-4o")
        old_key = litellm.api_key
        litellm.api_key = self.api_key
        
        try:
            response = litellm.completion(
                model=f"openai/{model_name}" if not model_name.startswith("openai/") else model_name,
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
                        "provider": "OpenAI",
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
