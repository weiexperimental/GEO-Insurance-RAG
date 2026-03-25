from dataclasses import dataclass
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class Settings:
    opensearch_host: str = "localhost"
    opensearch_port: int = 9200
    lightrag_api_url: str = "http://localhost:9621"
    log_dir: str = "./logs"
    host: str = "0.0.0.0"
    port: int = 8080
    # Model configs for LightRAG query support
    llm_model: str = "gpt-4o-mini"
    llm_api_key: str = ""
    llm_api_base: str = "https://yibuapi.com/v1"
    embedding_model: str = "text-embedding-3-large"
    embedding_api_key: str = ""
    embedding_api_base: str = "https://yibuapi.com/v1"


def load_settings() -> Settings:
    load_dotenv()
    return Settings(
        opensearch_host=os.getenv("OPENSEARCH_HOST", "localhost"),
        opensearch_port=int(os.getenv("OPENSEARCH_PORT", "9200")),
        lightrag_api_url=os.getenv("LIGHTRAG_API_URL", "http://localhost:9621"),
        log_dir=os.getenv("LOG_DIR", "./logs"),
        host=os.getenv("ADMIN_HOST", "0.0.0.0"),
        port=int(os.getenv("ADMIN_PORT", "8080")),
        llm_model=os.getenv("LLM_MODEL", "gpt-4o-mini"),
        llm_api_key=os.getenv("LLM_API_KEY", ""),
        llm_api_base=os.getenv("LLM_API_BASE", "https://yibuapi.com/v1"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "text-embedding-3-large"),
        embedding_api_key=os.getenv("EMBEDDING_API_KEY", ""),
        embedding_api_base=os.getenv("EMBEDDING_API_BASE", "https://yibuapi.com/v1"),
    )
