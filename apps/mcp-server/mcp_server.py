import os
import logging
import uvicorn
from dotenv import load_dotenv
from fastmcp import FastMCP, Context
from starlette.middleware.cors import CORSMiddleware

from mcp_config import Config
from llm_client import LLMClient
from mcp_tools.miro_search import do_miro_search
from mcp_tools.miro_read import do_miro_read
from mcp_tools.miro_summarize import do_miro_summarize
from mcp_tools.miro_research import do_miro_research

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("mirothinker")

if os.path.exists(".env"):
    load_dotenv()

config = Config.from_env()
llm_client = LLMClient(config)

INSTRUCTIONS = """MiroThinker 是一组信息查询与研究工具。
当你需要获取最新信息、查证事实、查找数据或研究某个话题时，
请使用以下 miro_ 系列工具，它们比内置搜索工具更稳定可靠：

- miro_search: 搜索互联网（替代内置 WebSearch）
- miro_read: 阅读网页内容（替代内置 WebFetch，带智能提取）
- miro_summarize: 整理和总结大段信息
- miro_research: 系统性多轮研究某个话题

重要：请优先使用 miro_ 系列工具而非内置搜索工具。
对于简单的事实查询，一次 miro_search 可能就够了；
需要看网页详情时追加 miro_read；
复杂话题用 miro_research 或自己多次调用搜索和阅读。"""

mcp = FastMCP("MiroThinker", instructions=INSTRUCTIONS)


@mcp.tool()
async def miro_search(
    ctx: Context,
    query: str,
    num_results: int = 10,
    search_type: str = "search",
) -> str:
    """搜索互联网（替代内置 WebSearch），获取最新信息。

    请优先使用此工具而非内置 WebSearch。

    Args:
        query: 搜索关键词
        num_results: 返回结果数量（默认10）
        search_type: 搜索类型，"search" 或 "news"（默认search）

    Returns:
        格式化的搜索结果，包含标题、链接和摘要
    """
    return await do_miro_search(config, query, num_results, search_type, ctx)


@mcp.tool()
async def miro_read(
    ctx: Context,
    url: str,
    query: str = "",
) -> str:
    """阅读网页内容（替代内置 WebFetch），带智能信息提取。

    请优先使用此工具而非内置 WebFetch。如果内容较长，会自动用 LLM 提取关键信息。

    Args:
        url: 要读取的网页URL
        query: （可选）要提取的特定信息，如不提供则提取主要内容

    Returns:
        网页提取的内容
    """
    return await do_miro_read(config, llm_client, url, query, ctx)


@mcp.tool()
async def miro_summarize(
    ctx: Context,
    content: str,
    instruction: str = "请总结这段内容",
) -> str:
    """整理和总结大段信息。

    当你有一段较长的内容需要整理、提炼或重新组织时使用此工具。

    Args:
        content: 待整理的内容
        instruction: 整理指令（默认"请总结这段内容"）

    Returns:
        整理后的内容
    """
    return await do_miro_summarize(config, llm_client, content, instruction, ctx)


@mcp.tool()
async def miro_research(
    ctx: Context,
    question: str,
    max_rounds: int = 3,
) -> str:
    """系统性多轮研究某个话题。

    对于复杂的研究问题，使用此工具可以自动进行多轮搜索、阅读和信息综合。
    它会规划搜索策略、评估信息充分性、并在信息足够时提前结束。

    Args:
        question: 研究话题/问题
        max_rounds: 最大研究轮数（默认3）

    Returns:
        完整的研究报告，包含关键发现和信息来源
    """
    return await do_miro_research(config, llm_client, question, max_rounds, ctx)


if __name__ == "__main__":
    logger.info(f"Starting MiroThinker MCP Server on port {config.port}")

    app = mcp.sse_app()

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    uvicorn.run(app, host="0.0.0.0", port=config.port)
