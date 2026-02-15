import asyncio
import json
import logging
from typing import Any, Dict

import httpx

from mcp_config import Config
from mcp_tools.utils import is_huggingface_dataset_or_space_url
from llm_client import LLMClient

logger = logging.getLogger("mirothinker")


async def do_miro_read(
    config: Config,
    llm_client: LLMClient,
    url: str,
    query: str = "",
    ctx: Any = None,
) -> str:
    if ctx:
        ctx.info(f"[MiroThinker] 📄 正在阅读网页: {url}")

    if is_huggingface_dataset_or_space_url(url):
        return "Error: You are trying to scrape a Hugging Face dataset or space URL."

    max_chars = 102400 * 4

    scrape_result = await scrape_url_with_jina(config, url, max_chars)

    if not scrape_result["success"]:
        if ctx:
            ctx.warning(f"[MiroThinker] ⚠️ Jina 抓取失败: {scrape_result['error']}，尝试直接访问...")
        scrape_result = await scrape_url_with_python(url, max_chars)

        if not scrape_result["success"]:
            if ctx:
                ctx.error(f"[MiroThinker] ❌ 抓取失败: {scrape_result['error']}")
            return f"Error: Scraping failed: {scrape_result['error']}"
        else:
            if ctx:
                ctx.info("[MiroThinker] ✅ Python fallback 抓取成功")

    content = scrape_result["content"]

    if len(content) <= 6000 and not query:
        if ctx:
            ctx.info(f"[MiroThinker] ✅ 内容提取完成 ({len(content)} 字)")
        return f"## 网页内容: {url}\n\n{content}"

    if ctx:
        ctx.info("[MiroThinker] 🤖 正在提取关键信息...")

    info_to_extract = query if query else "主要内容和关键信息"

    try:
        extracted = await llm_client.extract_info(
            content=content,
            info_to_extract=info_to_extract,
        )
    except Exception as e:
        if ctx:
            ctx.warning(f"[MiroThinker] ⚠️ LLM 提取失败: {e}，返回原始内容")
        extracted = content[:6000]
        if len(content) > 6000:
            extracted += "\n\n[...内容已截断...]"

    if ctx:
        ctx.info(f"[MiroThinker] ✅ 内容提取完成 ({len(content)} 字)")

    return f"## 网页内容: {url}\n\n{extracted}"


async def scrape_url_with_jina(
    config: Config, url: str, max_chars: int
) -> Dict[str, Any]:
    if not url or not url.strip():
        return {
            "success": False,
            "content": "",
            "error": "URL cannot be empty",
            "line_count": 0,
            "char_count": 0,
            "last_char_line": 0,
            "all_content_displayed": False,
        }

    if url.startswith("https://r.jina.ai/") and url.count("http") >= 2:
        url = url[len("https://r.jina.ai/") :]

    jina_url = f"{config.jina_base_url}/{url}"
    headers = {"Authorization": f"Bearer {config.jina_api_key}"}

    retry_delays = [1, 2, 4, 8]

    for attempt, delay in enumerate(retry_delays, 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    jina_url,
                    headers=headers,
                    timeout=httpx.Timeout(None, connect=20, read=60),
                    follow_redirects=True,
                )
                response.raise_for_status()
                break
        except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout) as e:
            if attempt < len(retry_delays):
                await asyncio.sleep(delay)
                continue
            return {
                "success": False,
                "content": "",
                "error": f"Connection error: {str(e)}",
                "line_count": 0,
                "char_count": 0,
                "last_char_line": 0,
                "all_content_displayed": False,
            }
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            should_retry = status_code >= 500 or status_code in [408, 409, 425, 429]
            if should_retry and attempt < len(retry_delays):
                await asyncio.sleep(delay)
                continue
            return {
                "success": False,
                "content": "",
                "error": f"HTTP {status_code}: {str(e)}",
                "line_count": 0,
                "char_count": 0,
                "last_char_line": 0,
                "all_content_displayed": False,
            }
        except Exception as e:
            return {
                "success": False,
                "content": "",
                "error": f"Unexpected error: {str(e)}",
                "line_count": 0,
                "char_count": 0,
                "last_char_line": 0,
                "all_content_displayed": False,
            }

    content = response.text

    if not content:
        return {
            "success": False,
            "content": "",
            "error": "No content returned",
            "line_count": 0,
            "char_count": 0,
            "last_char_line": 0,
            "all_content_displayed": False,
        }

    try:
        content_dict = json.loads(content)
        if (
            isinstance(content_dict, dict)
            and content_dict.get("name") == "InsufficientBalanceError"
        ):
            return {
                "success": False,
                "content": "",
                "error": "Insufficient balance",
                "line_count": 0,
                "char_count": 0,
                "last_char_line": 0,
                "all_content_displayed": False,
            }
    except json.JSONDecodeError:
        pass

    total_char_count = len(content)
    total_line_count = content.count("\n") + 1 if content else 0
    displayed_content = content[:max_chars]
    all_content_displayed = total_char_count <= max_chars
    last_char_line = displayed_content.count("\n") + 1 if displayed_content else 0

    return {
        "success": True,
        "content": displayed_content,
        "error": "",
        "line_count": total_line_count,
        "char_count": total_char_count,
        "last_char_line": last_char_line,
        "all_content_displayed": all_content_displayed,
    }


async def scrape_url_with_python(url: str, max_chars: int) -> Dict[str, Any]:
    if not url or not url.strip():
        return {
            "success": False,
            "content": "",
            "error": "URL cannot be empty",
            "line_count": 0,
            "char_count": 0,
            "last_char_line": 0,
            "all_content_displayed": False,
        }

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
    }

    retry_delays = [1, 2, 4]

    for attempt, delay in enumerate(retry_delays, 1):
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    url,
                    headers=headers,
                    timeout=httpx.Timeout(None, connect=20, read=60),
                    follow_redirects=True,
                )
                response.raise_for_status()
                break
        except (httpx.ConnectTimeout, httpx.ConnectError, httpx.ReadTimeout) as e:
            if attempt < len(retry_delays):
                await asyncio.sleep(delay)
                continue
            return {
                "success": False,
                "content": "",
                "error": f"Connection error: {str(e)}",
                "line_count": 0,
                "char_count": 0,
                "last_char_line": 0,
                "all_content_displayed": False,
            }
        except httpx.HTTPStatusError as e:
            status_code = e.response.status_code
            should_retry = status_code >= 500 or status_code in [408, 409, 425, 429]
            if should_retry and attempt < len(retry_delays):
                await asyncio.sleep(delay)
                continue
            return {
                "success": False,
                "content": "",
                "error": f"HTTP {status_code}: {str(e)}",
                "line_count": 0,
                "char_count": 0,
                "last_char_line": 0,
                "all_content_displayed": False,
            }
        except Exception as e:
            return {
                "success": False,
                "content": "",
                "error": f"Unexpected error: {str(e)}",
                "line_count": 0,
                "char_count": 0,
                "last_char_line": 0,
                "all_content_displayed": False,
            }

    content = response.text

    if not content:
        return {
            "success": False,
            "content": "",
            "error": "No content returned",
            "line_count": 0,
            "char_count": 0,
            "last_char_line": 0,
            "all_content_displayed": False,
        }

    total_char_count = len(content)
    total_line_count = content.count("\n") + 1 if content else 0
    displayed_content = content[:max_chars]
    all_content_displayed = total_char_count <= max_chars
    last_char_line = displayed_content.count("\n") + 1 if displayed_content else 0

    return {
        "success": True,
        "content": displayed_content,
        "error": "",
        "line_count": total_line_count,
        "char_count": total_char_count,
        "last_char_line": last_char_line,
        "all_content_displayed": all_content_displayed,
    }
