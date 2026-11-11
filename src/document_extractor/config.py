"""Settings read from environment variables (and a local ``.env`` file)."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

DEFAULT_HF_MODEL = "Qwen/Qwen2.5-7B-Instruct"
DEFAULT_HF_EMBED_MODEL = "BAAI/bge-m3"
DEFAULT_HF_OCR_MODEL = "florence-community/Florence-2-large"


def load_dotenv_if_present(path: str | os.PathLike | None = None) -> None:
    """Load ``.env`` from the working directory without overriding real env vars."""
    try:
        from dotenv import load_dotenv
    except ImportError:  # pragma: no cover - python-dotenv is a core dependency
        return
    load_dotenv(dotenv_path=path or Path.cwd() / ".env", override=False)


def _env(name: str, default: str = "") -> str:
    value = os.environ.get(name, default)
    return value.strip() if isinstance(value, str) else default


@dataclass
class Settings:
    backend: str = "hf"
    # api backend
    api_base: str = ""
    api_key: str = ""
    model: str = ""
    vision_model: str = ""
    embed_model: str = ""
    # hf backend
    hf_model: str = DEFAULT_HF_MODEL
    hf_embed_model: str = DEFAULT_HF_EMBED_MODEL
    hf_ocr_model: str = DEFAULT_HF_OCR_MODEL
    # shared
    retriever: str = "auto"  # auto | embed | bm25
    max_new_tokens: int = 512
    cache_dir: str = field(default_factory=lambda: _env("MS_CACHE_DIR", ".cache/results"))

    @classmethod
    def from_env(cls) -> "Settings":
        load_dotenv_if_present()
        return cls(
            backend=_env("MS_BACKEND", "hf").lower(),
            api_base=_env("MS_API_BASE"),
            api_key=_env("MS_API_KEY"),
            model=_env("MS_MODEL"),
            vision_model=_env("MS_VISION_MODEL"),
            embed_model=_env("MS_EMBED_MODEL"),
            hf_model=_env("MS_HF_MODEL", DEFAULT_HF_MODEL),
            hf_embed_model=_env("MS_HF_EMBED_MODEL", DEFAULT_HF_EMBED_MODEL),
            hf_ocr_model=_env("MS_HF_OCR_MODEL", DEFAULT_HF_OCR_MODEL),
            retriever=_env("MS_RETRIEVER", "auto").lower(),
            max_new_tokens=int(_env("MS_MAX_NEW_TOKENS", "512") or 512),
            cache_dir=_env("MS_CACHE_DIR", ".cache/results"),
        )

    @property
    def model_name(self) -> str:
        return self.model if self.backend == "api" else self.hf_model

    def validate(self) -> None:
        if self.backend not in {"api", "hf"}:
            raise ValueError(f"MS_BACKEND must be 'api' or 'hf', got {self.backend!r}")
        if self.backend == "api":
            missing = [n for n, v in (("MS_API_BASE", self.api_base), ("MS_MODEL", self.model)) if not v]
            if missing:
                raise ValueError(f"MS_BACKEND=api needs {', '.join(missing)} (see .env.example)")
