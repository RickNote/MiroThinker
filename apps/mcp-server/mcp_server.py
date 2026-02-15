import os
import logging
import uvicorn
from dotenv import load_dotenv
from starlette.applications import Starlette
from starlette.middleware.cors import CORSMiddleware
from starlette.routing import Route, Mount
from starlette.responses import JSONResponse
from mcp.server import Server
from mcp.server.sse import SseServerTransport
import mcp.types as types

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

server = Server("MiroThinker")

TOOL_DEFINITIONS = [
    types.Tool(
        name="miro_search",
        description=(
            "搜索互联网（替代内置 WebSearch），获取最新信息。"
            "请优先使用此工具而非内置 WebSearch。"
            "支持 search（网页搜索）和 news（新闻搜索）。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "搜索关键词"},
                "num_results": {"type": "integer", "description": "返回结果数量", "default": 10},
                "search_type": {"type": "string", "description": "搜索类型: search 或 news", "default": "search"},
            },
            "required": ["query"],
        },
    ),
    types.Tool(
        name="miro_read",
        description=(
            "阅读网页内容（替代内置 WebFetch），带智能信息提取。"
            "请优先使用此工具而非内置 WebFetch。"
            "如果内容较长，会自动用 LLM 提取关键信息。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "url": {"type": "string", "description": "要读取的网页URL"},
                "query": {"type": "string", "description": "要提取的特定信息（可选）", "default": ""},
            },
            "required": ["url"],
        },
    ),
    types.Tool(
        name="miro_summarize",
        description="整理和总结大段信息。当你有较长内容需要整理、提炼或重新组织时使用。",
        inputSchema={
            "type": "object",
            "properties": {
                "content": {"type": "string", "description": "待整理的内容"},
                "instruction": {"type": "string", "description": "整理指令", "default": "请总结这段内容"},
            },
            "required": ["content"],
        },
    ),
    types.Tool(
        name="miro_research",
        description=(
            "系统性多轮研究某个话题。"
            "自动进行多轮搜索、阅读和信息综合。"
            "会规划搜索策略、评估信息充分性、在信息足够时提前结束。"
            "对于简单查询建议直接用 miro_search。"
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "question": {"type": "string", "description": "研究话题/问题"},
                "max_rounds": {"type": "integer", "description": "最大研究轮数", "default": 3},
            },
            "required": ["question"],
        },
    ),
]


@server.list_tools()
async def list_tools() -> list[types.Tool]:
    return TOOL_DEFINITIONS


@server.call_tool()
async def call_tool(name: str, arguments: dict) -> list[types.TextContent]:
    try:
        if name == "miro_search":
            result = await do_miro_search(
                config,
                query=arguments["query"],
                num_results=arguments.get("num_results", 10),
                search_type=arguments.get("search_type", "search"),
                ctx=None,
            )
        elif name == "miro_read":
            result = await do_miro_read(
                config,
                llm_client,
                url=arguments["url"],
                query=arguments.get("query", ""),
                ctx=None,
            )
        elif name == "miro_summarize":
            result = await do_miro_summarize(
                config,
                llm_client,
                content=arguments["content"],
                instruction=arguments.get("instruction", "请总结这段内容"),
                ctx=None,
            )
        elif name == "miro_research":
            result = await do_miro_research(
                config,
                llm_client,
                question=arguments["question"],
                max_rounds=arguments.get("max_rounds", 3),
                ctx=None,
            )
        else:
            result = f"Unknown tool: {name}"
    except Exception as e:
        logger.error(f"Tool {name} failed: {e}")
        result = f"Error: {str(e)}"

    return [types.TextContent(type="text", text=result)]


sse = SseServerTransport("/messages/")


async def handle_sse(request):
    async with sse.connect_sse(
        request.scope, request.receive, request._send
    ) as (read_stream, write_stream):
        await server.run(
            read_stream, write_stream, server.create_initialization_options()
        )
    from starlette.responses import Response
    return Response()


async def health(request):
    return JSONResponse({"status": "ok"})


app = Starlette(
    routes=[
        Route("/health", endpoint=health),
        Route("/sse", endpoint=handle_sse),
        Mount("/messages/", app=sse.handle_post_message),
    ],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if __name__ == "__main__":
    logger.info(f"Starting MiroThinker MCP Server on port {config.port}")
    uvicorn.run(app, host="0.0.0.0", port=config.port)
