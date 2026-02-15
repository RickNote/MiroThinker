import logging
from typing import Any

from mcp_config import Config
from llm_client import LLMClient

logger = logging.getLogger("mirothinker")

SUMMARIZE_PROMPT = """你是一个信息整理专家。请根据用户的指令整理以下内容。

用户指令:
{}

待整理的内容:
{}

请按照用户的要求整理内容，保持信息的准确性和完整性。"""


async def do_miro_summarize(
    config: Config,
    llm_client: LLMClient,
    content: str,
    instruction: str = "请总结这段内容",
    ctx: Any = None,
) -> str:
    if ctx:
        ctx.info(f"[MiroThinker] 📝 正在整理内容 ({len(content)} 字)...")

    prompt = SUMMARIZE_PROMPT.format(instruction, content)

    result = await llm_client.chat(
        prompt,
        role="summary",
        temperature=0.3,
        max_tokens=8192,
    )

    if ctx:
        ctx.info("[MiroThinker] ✅ 内容整理完成")

    return result
