"""Secret resolution — env for dev; extend for AWS/GCP/Vault secret managers."""

from __future__ import annotations

import os
from abc import ABC, abstractmethod
from functools import lru_cache


class SecretProvider(ABC):
    @abstractmethod
    def get_secret(self, key: str) -> str | None:
        pass


class EnvSecretProvider(SecretProvider):
    """Read secrets from process environment (`.env` via pydantic-settings)."""

    def get_secret(self, key: str) -> str | None:
        v = os.environ.get(key)
        return v.strip() if v and v.strip() else None


class MappedSecretProvider(SecretProvider):
    """Map logical names to env keys — simulates secret-manager aliases."""

    def __init__(self, mapping: dict[str, str], fallback: SecretProvider | None = None):
        self._mapping = mapping
        self._fallback = fallback or EnvSecretProvider()

    def get_secret(self, key: str) -> str | None:
        env_key = self._mapping.get(key, key)
        return self._fallback.get_secret(env_key)


@lru_cache(maxsize=1)
def get_secret_provider(provider_name: str = "env") -> SecretProvider:
    name = (provider_name or "env").strip().lower()
    if name == "env":
        return EnvSecretProvider()
    if name == "mapped":
        return MappedSecretProvider(
            {
                "gemini_api_key": "GEMINI_API_KEY",
                "s3_secret_key": "SN_S3_SECRET_KEY",
                "webhook_signing_key": "SN_WEBHOOK_SIGNING_KEY",
            }
        )
    raise ValueError(f"unknown secret provider: {provider_name}")
