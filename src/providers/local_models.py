import json
import logging
import os
import threading
import urllib.request
from pathlib import Path
from typing import List, Dict, Any, Generator
from src.providers.base_provider import BaseProvider
from src.config import settings

logger = logging.getLogger(__name__)

class LocalModelProvider(BaseProvider):
    def list_models(self) -> List[Dict[str, Any]]:
        raise NotImplementedError

    def test_connection(self) -> bool:
        raise NotImplementedError

    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        raise NotImplementedError
        
    def generate_chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        raise NotImplementedError


try:
    from foundry_local_sdk import FoundryLocalManager, Configuration
except ImportError:
    FoundryLocalManager = None

class FoundryProvider(LocalModelProvider):
    """Microsoft Foundry Local adapter.

    The SDK manager is a process-wide singleton.  Keeping model instances here
    also prevents every HTTP request from loading the same model again.
    """

    _manager = None
    _manager_lock = threading.RLock()
    _inference_lock = threading.Lock()
    _loaded_models: Dict[str, Any] = {}
    _tokenizers: Dict[str, Any] = {}
    _tokenizer_lock = threading.Lock()

    def __init__(self, app_name: str = "ContextLite"):
        self.app_name = app_name

    @property
    def manager(self):
        return self._get_manager()

    @classmethod
    def _get_manager(cls):
        if FoundryLocalManager is None:
            raise RuntimeError(
                "Microsoft Foundry Local SDK kurulu değil. "
                "Windows için 'pip install foundry-local-sdk-winml' komutunu çalıştırın."
            )

        with cls._manager_lock:
            if cls._manager is not None:
                return cls._manager

            try:
                # Current Foundry Local SDK uses an initialize/instance singleton.
                try:
                    existing = FoundryLocalManager.instance
                except Exception:
                    existing = None
                if existing is None:
                    data_root = Path(settings.foundry_data_dir).resolve()
                    app_data_dir = data_root / "app"
                    model_cache_dir = data_root / "models"
                    logs_dir = data_root / "logs"
                    for directory in (app_data_dir, model_cache_dir, logs_dir):
                        directory.mkdir(parents=True, exist_ok=True)
                    FoundryLocalManager.initialize(Configuration(
                        app_name="ContextLite",
                        app_data_dir=str(app_data_dir),
                        model_cache_dir=str(model_cache_dir),
                        logs_dir=str(logs_dir),
                    ))
                    existing = FoundryLocalManager.instance
                cls._manager = existing
                return cls._manager
            except Exception as exc:
                logger.exception("FoundryLocalManager başlatılamadı")
                raise RuntimeError(
                    "Foundry Local başlatılamadı. Python 3.11+ ve resmi Foundry Local SDK "
                    f"kurulumunu kontrol edin. Ayrıntı: {exc}"
                ) from exc

    @staticmethod
    def _value(model: Any, *names: str, default=None):
        info = getattr(model, "info", None)
        for obj in (model, info):
            if obj is None:
                continue
            for name in names:
                value = getattr(obj, name, None)
                if value is not None:
                    return value
        return default

    @classmethod
    def _identifiers(cls, model: Any) -> set:
        values = {
            cls._value(model, "id"),
            cls._value(model, "alias"),
            cls._value(model, "name"),
        }
        return {str(value) for value in values if value}

    @classmethod
    def _display_id(cls, model: Any) -> str:
        return str(cls._value(model, "alias", "id", "name", default=str(model)))

    @classmethod
    def _task(cls, model: Any) -> str:
        task = cls._value(model, "task", default="")
        task = getattr(task, "value", task)
        return str(task).lower().replace("_", "-")

    @classmethod
    def _matches_task(cls, model: Any, requested_task: str) -> bool:
        task = cls._task(model)
        if requested_task == "embedding":
            return "embedding" in task
        # Some SDK/catalog versions omit task on the alias object.  Exclude only
        # models that are explicitly for another modality.
        return not task or "chat" in task or "text-generation" in task

    @classmethod
    def _model_keys(cls, models: List[Any]) -> set:
        keys = set()
        for model in models:
            keys.update(cls._identifiers(model))
        return keys

    @classmethod
    def _quality_key(cls, model: Any):
        """Prefer a capable Turkish model, then larger cached chat models."""
        text = " ".join(cls._identifiers(model)).lower()
        priorities = (
            "phi-4-mini",
            "phi-3.5-mini",
            "qwen3-4b",
            "qwen2.5-3b",
            "qwen2.5-1.5b",
            "qwen2.5-0.5b",
        )
        rank = next((len(priorities) - i for i, name in enumerate(priorities) if name in text), 0)
        size = cls._value(model, "file_size_mb", default=0) or 0
        try:
            size = int(size)
        except (TypeError, ValueError):
            size = 0
        return rank, size

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            manager = self.manager
            models = [m for m in manager.catalog.list_models() if self._matches_task(m, "chat")]
            try:
                cached_keys = self._model_keys(manager.catalog.get_cached_models())
            except Exception:
                cached_keys = set()
            try:
                loaded_keys = self._model_keys(manager.catalog.get_loaded_models())
            except Exception:
                loaded_keys = set()

            result = []
            for m in models:
                m_id = self._display_id(m)
                identifiers = self._identifiers(m)
                is_cached = bool(identifiers & cached_keys)
                is_loaded = bool(identifiers & loaded_keys) or m_id in self._loaded_models
                result.append({
                    "id": m_id,
                    "name": str(self._value(m, "name", "alias", default=m_id)),
                    "provider": "foundry",
                    "task": self._task(m) or "chat-completion",
                    "fileSizeMb": int(self._value(m, "file_size_mb", default=0) or 0),
                    "contextLength": int(self._value(m, "context_length", default=0) or 0),
                    "capabilities": str(self._value(m, "capabilities", default="") or ""),
                    "isCached": is_cached,
                    "isLoaded": is_loaded,
                    "isReady": is_loaded,
                    "status": "ready" if is_loaded else ("cached" if is_cached else "downloadable"),
                })
            result.sort(
                key=lambda item: (
                    not item["isLoaded"],
                    not item["isCached"],
                    -self._quality_key(next(m for m in models if self._display_id(m) == item["id"]))[0],
                    item["name"].lower(),
                )
            )
            return result
        except Exception as e:
            logger.error(f"Foundry model listeleme hatası: {str(e)}")
            return []

    def install_model(self, model_id: str, progress_callback=None, cancel_event=None) -> Dict[str, Any]:
        """Download a chat model into the configured local Foundry cache."""
        model = self._resolve_model(model_id, "chat")
        resolved_id = self._display_id(model)
        try:
            cached_keys = self._model_keys(self.manager.catalog.get_cached_models())
        except Exception:
            cached_keys = set()

        if not (self._identifiers(model) & cached_keys):
            model.download(progress_callback, cancel_event)
        elif progress_callback:
            progress_callback(100)

        return {
            "id": resolved_id,
            "name": str(self._value(model, "name", "alias", default=resolved_id)),
            "fileSizeMb": int(self._value(model, "file_size_mb", default=0) or 0),
            "status": "cached",
        }

    def remove_model(self, model_id: str) -> Dict[str, Any]:
        """Unload a chat model and remove its files from the Foundry cache."""
        model = self._resolve_model(model_id, "chat")
        resolved_id = self._display_id(model)
        identifiers = self._identifiers(model)

        with self._inference_lock:
            try:
                loaded_keys = self._model_keys(self.manager.catalog.get_loaded_models())
            except Exception:
                loaded_keys = set()
            if identifiers & loaded_keys or resolved_id in self._loaded_models:
                model.unload()
            model.remove_from_cache()

        with self._manager_lock:
            for key in list(self._loaded_models):
                if key == resolved_id or key in identifiers:
                    self._loaded_models.pop(key, None)

        return {"id": resolved_id, "status": "removed"}

    def _resolve_model(self, model_id: str = None, requested_task: str = "chat"):
        manager = self.manager
        catalog = manager.catalog

        if model_id:
            try:
                model = catalog.get_model(model_id)
                if model is not None and self._matches_task(model, requested_task):
                    return model
            except Exception:
                pass
            for model in catalog.list_models():
                if model_id in self._identifiers(model) and self._matches_task(model, requested_task):
                    return model
            raise RuntimeError(f"'{model_id}' modeli Foundry Local kataloğunda bulunamadı.")

        env_name = "FOUNDRY_EMBEDDING_MODEL" if requested_task == "embedding" else "FOUNDRY_CHAT_MODEL"
        configured = os.getenv(env_name, "").strip()
        if not configured:
            configured = (
                settings.foundry_embedding_model
                if requested_task == "embedding"
                else settings.foundry_chat_model
            ).strip()
        if configured:
            return self._resolve_model(configured, requested_task)

        models = [m for m in catalog.list_models() if self._matches_task(m, requested_task)]
        if not models:
            label = "embedding" if requested_task == "embedding" else "sohbet"
            raise RuntimeError(f"Foundry Local kataloğunda {label} modeli bulunamadı.")

        try:
            loaded = [m for m in catalog.get_loaded_models() if self._matches_task(m, requested_task)]
        except Exception:
            loaded = []
        if loaded:
            return max(loaded, key=self._quality_key)

        try:
            cached = [m for m in catalog.get_cached_models() if self._matches_task(m, requested_task)]
        except Exception:
            cached = []
        if cached:
            return max(cached, key=self._quality_key)

        preferred = "qwen3-embedding-0.6b" if requested_task == "embedding" else "phi-3.5-mini"
        for model in models:
            if preferred in " ".join(self._identifiers(model)).lower():
                return model
        return max(models, key=self._quality_key)

    def _prepare_model(self, model_id: str = None, requested_task: str = "chat"):
        model = self._resolve_model(model_id, requested_task)
        key = self._display_id(model)
        with self._manager_lock:
            if key in self._loaded_models:
                return self._loaded_models[key], key

            manager = self.manager
            try:
                loaded_keys = self._model_keys(manager.catalog.get_loaded_models())
            except Exception:
                loaded_keys = set()
            if not (self._identifiers(model) & loaded_keys):
                try:
                    cached_keys = self._model_keys(manager.catalog.get_cached_models())
                except Exception:
                    cached_keys = set()
                if not (self._identifiers(model) & cached_keys):
                    model.download()
                model.load()

            self._loaded_models[key] = model
            return model, key

    @staticmethod
    def _clean_messages(messages: List[Dict[str, str]]) -> List[Dict[str, str]]:
        clean = []
        for message in messages:
            role = message.get("role", "user")
            content = str(message.get("content", "")).replace("/no_think", "").strip()
            if content:
                clean.append({"role": role, "content": content})
        return clean

    @staticmethod
    def _configure_client(client: Any, temperature: float, max_tokens: int):
        settings = getattr(client, "settings", None)
        if settings is not None:
            if hasattr(settings, "temperature"):
                settings.temperature = temperature
            if hasattr(settings, "max_tokens"):
                settings.max_tokens = max_tokens

    def test_connection(self, model_id: str = None) -> bool:
        # A catalog listing is not a readiness test; perform real inference.
        result = self.generate_chat(
            [{"role": "user", "content": "Yalnızca OK yaz."}],
            model=model_id,
            temperature=0.0,
            max_tokens=8,
        )
        if not result.strip():
            raise RuntimeError("Foundry Local modeli boş yanıt döndürdü.")
        return True

    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        return "".join(
            item.get("content", "")
            for item in self.generate_chat_stream(messages, **kwargs)
            if item.get("content")
        ).strip()

    def count_tokens(self, text: str, model_id: str = None) -> int:
        """Count raw text with the exact tokenizer shipped with a cached model."""
        model = self._resolve_model(model_id, "chat")
        model_path = Path(model.get_path()).resolve()
        tokenizer_path = model_path / "tokenizer.json"
        if not tokenizer_path.is_file():
            matches = list(model_path.rglob("tokenizer.json")) if model_path.is_dir() else []
            if not matches:
                raise RuntimeError(
                    f"'{self._display_id(model)}' için tokenizer.json bulunamadı."
                )
            tokenizer_path = matches[0]

        cache_key = str(tokenizer_path)
        with self._tokenizer_lock:
            tokenizer = self._tokenizers.get(cache_key)
            if tokenizer is None:
                from tokenizers import Tokenizer

                tokenizer = Tokenizer.from_file(cache_key)
                self._tokenizers[cache_key] = tokenizer

        return len(tokenizer.encode(str(text or ""), add_special_tokens=False).ids)

    def generate_chat_stream(self, messages: List[Dict[str, str]], **kwargs) -> Generator[Dict[str, Any], None, None]:
        model, resolved_id = self._prepare_model(kwargs.get("model"), "chat")
        temperature = float(kwargs.get("temperature", 0.2))
        max_tokens = int(kwargs.get("max_tokens", 1000))
        clean_messages = self._clean_messages(messages)
        if not clean_messages:
            raise ValueError("Sohbet mesajı boş olamaz.")

        with self._inference_lock:
            client = model.get_chat_client()
            self._configure_client(client, temperature, max_tokens)
            if hasattr(client, "complete_streaming_chat"):
                for chunk in client.complete_streaming_chat(clean_messages):
                    # Some SDK releases emit a terminal chunk with no choices.
                    choices = getattr(chunk, "choices", None) or []
                    if not choices:
                        continue
                    delta = getattr(choices[0], "delta", None)
                    content = getattr(delta, "content", None) if delta is not None else None
                    if content:
                        yield {"content": content, "model": resolved_id}
                return

            response = client.complete_chat(clean_messages)
            choices = getattr(response, "choices", None) or []
            if not choices:
                raise RuntimeError("Foundry Local modeli geçerli bir yanıt döndürmedi.")
            message = getattr(choices[0], "message", None)
            content = getattr(message, "content", None) if message is not None else None
            if not content:
                content = getattr(choices[0], "text", None)
            if content:
                yield {"content": str(content), "model": resolved_id}

    def generate_embeddings(self, texts: List[str], model_id: str = None):
        clean_texts = [str(text).strip() for text in texts if str(text).strip()]
        if not clean_texts:
            return [], None
        model, resolved_id = self._prepare_model(model_id, "embedding")
        with self._inference_lock:
            client = model.get_embedding_client()
            if hasattr(client, "generate_embeddings"):
                response = client.generate_embeddings(clean_texts)
                return [list(item.embedding) for item in response.data], resolved_id
            embeddings = []
            for text in clean_texts:
                response = client.generate_embedding(text)
                embeddings.append(list(response.data[0].embedding))
            return embeddings, resolved_id


class LMStudioProvider(LocalModelProvider):
    def __init__(self, base_url: str = "http://127.0.0.1:1234/v1"):
        self.base_url = base_url

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            req = urllib.request.Request(f"{self.base_url}/models")
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                models = data.get("data", [])
                return [{
                    "id": m["id"],
                    "name": m.get("id", m["id"]).split("/")[-1],
                    "provider": "lm_studio",
                    "isCached": True,
                    "isLoaded": True
                } for m in models]
        except Exception:
            return []

    def test_connection(self) -> bool:
        try:
            models = self.list_models()
            if not models:
                raise Exception("LM Studio'da yüklü model bulunamadı.")
            return True
        except Exception as e:
            raise Exception(f"LM Studio bağlantı hatası: {str(e)}")

    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        model_id = kwargs.get("model")
        temperature = kwargs.get("temperature", 0.7)
        payload = json.dumps({
            "model": model_id,
            "messages": messages,
            "temperature": temperature,
            "stream": False
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode())
                return data["choices"][0]["message"]["content"]
        except Exception as e:
            raise Exception(f"LM Studio API Hatası: {str(e)}")


class OllamaProvider(LocalModelProvider):
    def __init__(self, base_url: str = "http://127.0.0.1:11434/api"):
        self.base_url = base_url

    def list_models(self) -> List[Dict[str, Any]]:
        try:
            req = urllib.request.Request(f"{self.base_url}/tags")
            with urllib.request.urlopen(req, timeout=3) as response:
                data = json.loads(response.read().decode())
                models = data.get("models", [])
                return [{
                    "id": m["name"],
                    "name": m["name"],
                    "provider": "ollama",
                    "isCached": True,
                    "isLoaded": True
                } for m in models]
        except Exception:
            return []

    def test_connection(self) -> bool:
        try:
            models = self.list_models()
            if not models:
                raise Exception("Ollama'da model bulunamadı.")
            return True
        except Exception as e:
            raise Exception(f"Ollama bağlantı hatası: {str(e)}")

    def generate_chat(self, messages: List[Dict[str, str]], **kwargs) -> str:
        model_id = kwargs.get("model")
        temperature = kwargs.get("temperature", 0.7)
        payload = json.dumps({
            "model": model_id,
            "messages": messages,
            "stream": False,
            "options": {"temperature": temperature}
        }).encode("utf-8")

        req = urllib.request.Request(
            f"{self.base_url}/chat",
            data=payload,
            headers={"Content-Type": "application/json"}
        )
        try:
            with urllib.request.urlopen(req, timeout=120) as response:
                data = json.loads(response.read().decode())
                return data.get("message", {}).get("content", "")
        except Exception as e:
            raise Exception(f"Ollama API Hatası: {str(e)}")
