# src/metadata.py
import json
from typing import Any

from lightrag.llm.openai import openai_complete_if_cache

from src.config import ModelConfig

EXTRACTION_PROMPT = """你是一個香港保險文件分析助手。請從以下文件內容中提取結構化資訊。

規則：
- 每個欄位必須從文件內容或檔案名中提取真實值，絕對不可以填寫範例文字或佔位符
- 如果文件內容中找不到某個欄位的資訊，請填空字串 ""
- company 必須是真實的保險公司中文全名（例如：中銀人壽保險有限公司、周大福人壽保險有限公司、立橋人壽保險有限公司、安盛保險有限公司）
- 如果文件內容沒有明確寫出公司名，可以從檔案名推斷（例如 BOCLife = 中銀人壽、CTFLife = 周大福人壽、AXA = 安盛）
- product_name 必須是文件中提到的具體產品名稱，不可以是泛稱
- product_type 只能填以下其中一個：醫療、儲蓄、人壽、危疾、意外、年金、其他
- document_type 只能填以下其中一個：產品小冊子、宣傳單張、付款指引、培訓資料、報價單、其他

只回傳 JSON，不要其他文字：
{
    "company": "",
    "product_name": "",
    "product_type": "",
    "document_type": "",
    "document_date": ""
}

檔案名：{file_name}

文件內容：
"""


async def extract_metadata(content: str, llm_config: ModelConfig, file_name: str = "") -> dict[str, Any]:
    """Extract structured metadata from document content using LLM."""
    try:
        truncated = content[:8000]
        prompt = EXTRACTION_PROMPT.replace("{file_name}", file_name) + truncated
        response = await openai_complete_if_cache(
            model=llm_config.model,
            prompt=prompt,
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
