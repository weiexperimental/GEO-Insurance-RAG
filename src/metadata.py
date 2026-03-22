# src/metadata.py
import json
from typing import Any

from lightrag.llm.openai import openai_complete_if_cache

from src.config import ModelConfig

EXTRACTION_PROMPT = """你是一個保險文件分析助手。請從以下文件內容中提取結構化資訊。

只回傳 JSON，不要其他文字。格式如下：
{
    "company": "保險公司名稱（中文全名）",
    "product_name": "產品名稱（中文）",
    "product_type": "產品類型：醫療 / 儲蓄 / 人壽 / 意外 / 其他",
    "document_type": "文件類型：產品小冊子 / 宣傳單張 / 付款指引 / 培訓資料 / 其他",
    "document_date": "文件日期（格式：YYYY-MM，如果找不到就填空字串）"
}

文件內容（前 3000 字）：
"""


async def extract_metadata(content: str, llm_config: ModelConfig) -> dict[str, Any]:
    """Extract structured metadata from document content using LLM."""
    try:
        truncated = content[:3000]
        response = await openai_complete_if_cache(
            model=llm_config.model,
            prompt=EXTRACTION_PROMPT + truncated,
            api_key=llm_config.api_key,
            base_url=llm_config.api_base,
        )
        # Parse JSON from response, handling potential markdown wrapping
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1].rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        return {}
