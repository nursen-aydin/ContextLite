import litellm
import json
from src.services.db import get_provider_key
from src.services.crypto import decrypt_key
from typing import List, Dict, Generator, Any
from src.providers.models import MODEL_CATALOG

class ProviderError(Exception):
    def __init__(self, category: str, code: str, message: str):
        self.category = category
        self.code = code
        self.message = message
        super().__init__(self.message)

def classify_litellm_error(e: Exception) -> ProviderError:
    err_str = str(e).lower()
    
    if "api key" in err_str or "authentication" in err_str or "invalid_api_key" in err_str or "401" in err_str:
        return ProviderError("invalid_api_key", "invalid_api_key", "API anahtarı geçersiz veya yetkilendirme başarısız.")
        
    if "rate limit" in err_str or "429" in err_str or "quota" in err_str:
        if "insufficient_quota" in err_str or "credit_balance_exhausted" in err_str or "billing" in err_str:
            return ProviderError(
                "billing_required", 
                "credit_balance_exhausted", 
                "OpenAI API hesabınızda kullanılabilir kredi bulunmuyor. ChatGPT aboneliği API kullanımını kapsamaz. OpenAI API faturalandırma ayarlarından ödeme yöntemi veya kredi ekledikten sonra bağlantıyı yeniden test edebilirsiniz."
            )
        elif "usage_limit" in err_str:
            return ProviderError("usage_limit_reached", "usage_limit", "Harcama limitinize ulaştınız.")
        else:
            return ProviderError("rate_limited", "rate_limit", "Geçici hız sınırı aşıldı. Lütfen daha sonra tekrar deneyin.")
            
    if "context window" in err_str or "context length" in err_str:
        return ProviderError("context_exceeded", "context_length_exceeded", "Gönderilen metin çok uzun.")
        
    if "model" in err_str and ("not found" in err_str or "does not exist" in err_str):
        return ProviderError("model_unavailable", "model_not_found", "Seçilen model kullanılamıyor veya hesabınıza açık değil.")
        
    return ProviderError("network_error", "unknown", f"Bağlantı kurulamadı veya bir sunucu hatası oluştu.")

litellm.telemetry = False
litellm.suppress_debug_info = True

def get_api_key(user_id: int, provider: str) -> str:
    encrypted = get_provider_key(user_id, provider)
    return decrypt_key(encrypted) if encrypted else ""

class LiteLLMRouter:
    def __init__(self):
        pass

    def is_provider_configured(self, user_id: int, provider: str) -> bool:
        if provider == "local_qwen": return True
        return bool(get_api_key(user_id, provider))

    def get_routing_plan(self, mode: str, custom_model: str, user_id: int) -> List[Dict[str, Any]]:
        """
        Returns a list of models to try, in order of priority, based on the mode.
        Each item is a dict with model info and a 'reason' for why it was selected.
        """
        if mode == "Modeli kendim seçerim" and custom_model:
            # We don't know the exact specs if it's not in catalog, but we assume it's paid unless known
            cat = MODEL_CATALOG.get(custom_model, {
                "id": custom_model,
                "provider": custom_model.split("/")[0] if "/" in custom_model else "openai",
                "is_free": False,
                "is_local": False
            })
            return [{"model": custom_model, "is_free": cat["is_free"], "reason": "Kullanıcı tarafından manuel olarak seçildi."}]

        # Filter available models
        available_models = []
        for model_id, info in MODEL_CATALOG.items():
            if self.is_provider_configured(user_id, info["provider"]):
                available_models.append(info)

        if not available_models:
            raise Exception("Bağlı hiçbir sağlayıcı bulunamadı. Lütfen ayarlardan API anahtarı ekleyin.")

        plan = []
        
        if mode == "Yalnızca Yerel" or mode == "Sadece Yerel":
            local_models = [m for m in available_models if m["is_local"]]
            if not local_models:
                raise Exception("Yerel model kullanılamıyor.")
            for m in local_models:
                plan.append({"model": m["id"], "is_free": True, "reason": "Sadece Yerel mod seçili olduğu için yerel model kullanılıyor."})
            return plan

        if mode == "Yalnızca Ücretsiz" or mode == "Sadece Ücretsiz":
            free_models = [m for m in available_models if m["is_free"]]
            # Prioritize local first, then cloud free
            free_models.sort(key=lambda x: (not x["is_local"], x["input_cost_per_m"]))
            if not free_models:
                raise Exception("Kullanılabilir ücretsiz model veya yerel model bulunamadı.")
            for m in free_models:
                reason = "Yerel model olduğu için seçildi." if m["is_local"] else "Ücretsiz API kotası olduğu için seçildi."
                plan.append({"model": m["id"], "is_free": True, "reason": reason})
            return plan

        if mode == "En İyi Yanıt" or mode == "En İyi Cevap":
            # Smartest first
            smart_models = [m for m in available_models if "smart" in m.get("tags", [])]
            smart_models.sort(key=lambda x: (x["is_free"], -x["input_cost_per_m"]), reverse=True)
            # If no smart models, fallback to fast
            fast_models = [m for m in available_models if "fast" in m.get("tags", []) and m not in smart_models]
            fast_models.sort(key=lambda x: (x["is_free"], x["input_cost_per_m"]), reverse=True)
            
            for m in smart_models + fast_models:
                reason = "Ücretsiz yüksek kapasiteli model" if m["is_free"] else "En iyi yanıt kapasitesine sahip model"
                plan.append({"model": m["id"], "is_free": m["is_free"], "reason": reason})
            return plan

        # Default: Akıllı Tasarruf / En Ekonomik
        # Priority: 1. Free Local, 2. Free Cloud, 3. Cheap Paid
        local_free = [m for m in available_models if m["is_local"]]
        cloud_free = [m for m in available_models if m["is_free"] and not m["is_local"]]
        paid = [m for m in available_models if not m["is_free"]]
        paid.sort(key=lambda x: x["input_cost_per_m"])
        
        for m in local_free:
            plan.append({"model": m["id"], "is_free": True, "reason": "Yerel ve ücretsiz olduğu için seçildi."})
        for m in cloud_free:
            plan.append({"model": m["id"], "is_free": True, "reason": "Ücretsiz bulut kotası olduğu için seçildi."})
        for m in paid:
            plan.append({"model": m["id"], "is_free": False, "reason": "Görev için uygun en ekonomik ücretli model olduğu için seçildi."})
            
        return plan

    def setup_api_keys(self, model_name: str, user_id: int):
        provider = model_name.split("/")[0] if "/" in model_name else "openai"
        if provider == "local_qwen": return
        if provider == "gemini":
            litellm.api_key = get_api_key(user_id, "gemini")
        elif provider == "openrouter":
            litellm.api_key = get_api_key(user_id, "openrouter")
        else:
            litellm.api_key = get_api_key(user_id, provider)

    def generate_chat_stream_single(self, messages: List[Dict[str, str]], model_name: str, is_free: bool, **kwargs):
        user_id = kwargs.get("user_id")
        self.setup_api_keys(model_name, user_id)
        provider = model_name.split("/")[0] if "/" in model_name else "Unknown"
        
        try:
            response = litellm.completion(
                model=model_name,
                messages=messages,
                stream=True,
                stream_options={"include_usage": True},
                temperature=kwargs.get("temperature", 0.7),
                max_tokens=kwargs.get("max_tokens", 1000)
            )
            
            for chunk in response:
                content = chunk.choices[0].delta.content if chunk.choices else ""
                usage = getattr(chunk, "usage", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_tokens", 0)
                    completion_tokens = getattr(usage, "completion_tokens", 0)
                    try:
                        cost = litellm.completion_cost(completion_response=chunk) if not is_free else 0.0
                    except:
                        cost = None
                    yield {
                        "is_metadata": True,
                        "provider": provider.capitalize(),
                        "model": model_name,
                        "location": "Bulut (Cloud)",
                        "prompt_tokens": prompt_tokens,
                        "completion_tokens": completion_tokens,
                        "cost": cost,
                        "is_free": is_free
                    }
                elif content:
                    yield {"content": content}
        except Exception as e:
            raise classify_litellm_error(e)

    def test_connection(self, provider: str, api_key: str) -> bool:
        test_model_map = {
            "openai": "openai/gpt-3.5-turbo",
            "gemini": "gemini/gemini-1.5-flash",
            "anthropic": "anthropic/claude-3-haiku-20240307",
            "openrouter": "openrouter/google/gemma-7b-it:free",
            "groq": "groq/llama3-8b-8192",
            "mistral": "mistral/mistral-tiny"
        }
        
        model_name = test_model_map.get(provider)
        if not model_name:
            raise Exception("Desteklenmeyen sağlayıcı testi.")
            
        old_key = litellm.api_key
        litellm.api_key = api_key
        try:
            litellm.completion(
                model=model_name,
                messages=[{"role": "user", "content": "test"}],
                max_tokens=1
            )
            return True
        except Exception as e:
            raise classify_litellm_error(e)
        finally:
            litellm.api_key = old_key
