import asyncio
import logging
from typing import Any, List, Dict

import httpx

from mcp_config import Config
from mcp_tools.utils import decode_http_urls_in_dict, is_huggingface_dataset_or_space_url

logger = logging.getLogger("mirothinker")


async def _raw_search(
    config: Config,
    query: str,
    num_results: int = 10,
    search_type: str = "search",
    ctx: Any = None,
) -> List[Dict]:
    """内部函数：执行搜索并返回结构化的原始结果。"""
    if ctx:
        ctx.info(f"[MiroThinker] 🔍 正在搜索: {query}")

    url = f"{config.serper_base_url}/search"
    headers = {
        "X-API-KEY": config.serper_api_key,
        "Content-Type": "application/json",
    }
    payload = {
        "q": query.strip(),
        "gl": "us",
        "hl": "en",
        "num": num_results,
    }

    if search_type == "news":
        payload["tbs"] = "qdr:w"

    retry_delays = [4, 7, 10]
    data: Dict[str, Any] = {}

    for attempt, delay in enumerate(retry_delays, 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(url, json=payload, headers=headers, timeout=30)
                response.raise_for_status()
                data = response.json()
                break
        except (httpx.ConnectError, httpx.Timeout, httpx.HTTPStatusError) as e:
            if attempt < len(retry_delays):
                await asyncio.sleep(delay)
                continue
            raise

    organic_results = []
    for item in data.get("organic", []):
        if is_huggingface_dataset_or_space_url(item.get("link", "")):
            continue
        organic_results.append(item)

    organic_results = decode_http_urls_in_dict(organic_results)

    if len(organic_results) == 0 and '"' in query:
        if ctx:
            ctx.info("[MiroThinker] 无结果，尝试去掉引号重新搜索...")
        new_query = query.replace('"', "")
        return await _raw_search(config, new_query, num_results, search_type, ctx)

    return organic_results


async def do_miro_search(
    config: Config,
    query: str,
    num_results: int = 10,
    search_type: str = "search",
    ctx: Any = None,
) -> str:
    """搜索互联网，获取最新信息。"""
    organic_results = await _raw_search(config, query, num_results, search_type, ctx)

    output = []
    output.append(f'## 搜索结果: "{query}"')
    output.append(f"共找到 {len(organic_results)} 条结果\n")

    for i, item in enumerate(organic_results, 1):
        title = item.get("title", "")
        link = item.get("link", "")
        snippet = item.get("snippet", "")
        output.append(f"{i}. **{title}**")
        output.append(f"   链接: {link}")
        output.append(f"   摘要: {snippet}\n")

    result_text = "\n".join(output)

    if ctx:
        ctx.info(f"[MiroThinker] ✅ 搜索完成，找到 {len(organic_results)} 条结果")

    return result_text
