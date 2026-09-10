"""Backwards-compatible imports for the original provider module."""

from src.providers.local_models import FoundryProvider

FoundryLocalProvider = FoundryProvider
LocalQwenProvider = FoundryProvider

__all__ = ["FoundryProvider", "FoundryLocalProvider", "LocalQwenProvider"]
