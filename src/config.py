# src/config.py
import os
from dataclasses import dataclass

from dotenv import load_dotenv


@dataclass
class ModelConfig:
    model: str
    api_key: str
    api_base: str


@dataclass
class OpenSearchConfig:
    host: str
    port: int


@dataclass
class MinerUConfig:
    device: str
    lang: str
    parse_method: str


@dataclass
class PathsConfig:
    inbox_dir: str
    processed_dir: str
    failed_dir: str
    log_dir: str


@dataclass
class LimitsConfig:
    max_file_size_mb: int


@dataclass
class AppConfig:
    llm: ModelConfig
    embedding: ModelConfig
    vision: ModelConfig
    opensearch: OpenSearchConfig
    mineru: MinerUConfig
    paths: PathsConfig
    limits: LimitsConfig


def _require_env(key: str) -> str:
    val = os.environ.get(key)
    if not val:
        raise ValueError(f"Missing required environment variable: {key}")
    return val


def load_config() -> AppConfig:
    load_dotenv()

    return AppConfig(
        llm=ModelConfig(
            model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
            api_key=_require_env("LLM_API_KEY"),
            api_base=os.getenv("LLM_API_BASE", "https://yibuapi.com/v1"),
        ),
        embedding=ModelConfig(
            model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
            api_key=_require_env("EMBEDDING_API_KEY"),
            api_base=os.getenv("EMBEDDING_API_BASE", "https://yibuapi.com/v1"),
        ),
        vision=ModelConfig(
            model=os.getenv("VISION_MODEL", "gpt-4o-mini"),
            api_key=_require_env("VISION_API_KEY"),
            api_base=os.getenv("VISION_API_BASE", "https://yibuapi.com/v1"),
        ),
        opensearch=OpenSearchConfig(
            host=os.getenv("OPENSEARCH_HOST", "localhost"),
            port=int(os.getenv("OPENSEARCH_PORT", "9200")),
        ),
        mineru=MinerUConfig(
            device=os.getenv("MINERU_DEVICE", "mps"),
            lang=os.getenv("MINERU_LANG", "ch"),
            parse_method=os.getenv("MINERU_PARSE_METHOD", "auto"),
        ),
        paths=PathsConfig(
            inbox_dir=os.getenv("INBOX_DIR", "./data/inbox"),
            processed_dir=os.getenv("PROCESSED_DIR", "./data/processed"),
            failed_dir=os.getenv("FAILED_DIR", "./data/failed"),
            log_dir=os.getenv("LOG_DIR", "./logs"),
        ),
        limits=LimitsConfig(
            max_file_size_mb=int(os.getenv("MAX_FILE_SIZE_MB", "100")),
        ),
    )
