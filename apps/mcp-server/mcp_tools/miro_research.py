import asyncio
import logging
from typing import Any, List, Dict, Set

from mcp_config import Config
from llm_client import LLMClient
from mcp_tools.miro_search import do_miro_search
from mcp_tools.miro_read import do_miro_read

logger = logging.getLogger("mirothinker")

RESEARCH_PLAN_PROMPT = """你是一个研究助手。用户想研究以下话题：

研究话题: {question}

请规划一系列搜索查询来帮助研究这个话题。请以 JSON 格式返回搜索查询列表，格式如下：
{{
  "search_queries": [
    "第一个搜索查询",
    "第二个搜索查询",
    "第三个搜索查询"
  ]
}}

最多返回 5 个搜索查询，要从不同角度覆盖这个话题。"""

ANALYZE_RESULTS_PROMPT = """你是一个研究助手。我们正在研究以下话题：

研究话题: {question}

以下是搜索结果和网页内容：

{content}

请分析这些信息，找出：
1. 最相关和最可靠的信息源
2. 关键发现
3. 可能需要进一步搜索的信息缺口

请以 JSON 格式返回：
{{
  "key_findings": [
    {{
      "finding": "发现内容",
      "source_url": "来源URL"
    }}
  ],
  "further_search_queries": ["补充搜索1", "补充搜索2"],
  "urls_to_read": ["需要阅读的URL1", "需要阅读的URL2"]
}}

只返回 JSON，不要其他内容。"""

SYNTHESIZE_PROMPT = """你是一个研究助手。请综合以下研究结果：

研究话题: {question}

收集到的信息:
{all_info}

请整理一个清晰的研究总结，包括：
1. 关键发现列表（注明来源）
2. 各信息源的详细内容
3. 研究过程统计

格式请参考：
## 关键发现
1. [发现内容] — 来源: [URL]
2. ...

## 各信息源详情
### 来源: [标题] ([URL])
[内容]

---
### 查询过程统计
- 搜索轮数: X
- 搜索关键词: X 个
- 访问网页: X 个
- 有效信息源: X 个

### 信息来源
1. [标题](URL)
2. ..."""


async def do_miro_research(
    config: Config,
    llm_client: LLMClient,
    question: str,
    max_rounds: int = 3,
    ctx: Any = None,
) -> str:
    if ctx:
        ctx.info(f"[MiroThinker] 🔬 开始系统性研究: {question}")
        ctx.report_progress(0, max_rounds)

    all_findings = []
    all_sources = []
    visited_urls: Set[str] = set()
    search_count = 0
    read_count = 0

    for round_num in range(max_rounds):
        if ctx:
            ctx.info(f"[MiroThinker] 🔄 研究轮次 {round_num + 1}/{max_rounds}")
            ctx.report_progress(round_num + 1, max_rounds)

        if round_num == 0:
            plan_result = await llm_client.chat_json(
                RESEARCH_PLAN_PROMPT.format(question=question),
                role="main",
                temperature=0.7,
            )
            search_queries = plan_result.get("search_queries", [question])
        else:
            search_queries = [f"{question} 更新信息"]

        for query in search_queries[:2]:
            search_count += 1
            search_result = await do_miro_search(config, query, num_results=5, ctx=ctx)

            urls_in_result = []
            for line in search_result.split("\n"):
                if line.strip().startswith("链接:"):
                    url = line.strip()[len("链接:") :].strip()
                    if url and url not in visited_urls:
                        urls_in_result.append(url)

            for url in urls_in_result[:2]:
                if url in visited_urls:
                    continue
                visited_urls.add(url)
                read_count += 1

                try:
                    read_result = await do_miro_read(
                        config, llm_client, url, query=question, ctx=ctx
                    )
                    all_sources.append({"url": url, "content": read_result})
                except Exception as e:
                    logger.warning(f"Failed to read {url}: {e}")
                    continue

        await asyncio.sleep(1)

    if ctx:
        ctx.info("[MiroThinker] 📊 正在综合研究结果...")

    all_info_text = "\n\n".join(
        [f"来源 {i+1} ({s['url']}):\n{s['content']}" for i, s in enumerate(all_sources)]
    )

    final_summary = await llm_client.chat(
        SYNTHESIZE_PROMPT.format(question=question, all_info=all_info_text),
        role="main",
        temperature=0.3,
        max_tokens=8192,
    )

    stats_section = f"""
---
### 查询过程统计
- 搜索轮数: {max_rounds}
- 搜索关键词: {search_count} 个
- 访问网页: {read_count} 个
- 有效信息源: {len(all_sources)} 个

### 信息来源
"""
    for i, s in enumerate(all_sources, 1):
        stats_section += f"{i}. {s['url']}\n"

    if ctx:
        ctx.info("[MiroThinker] ✅ 研究完成")

    return f"## 调查结果: {question}\n\n{final_summary}\n{stats_section}"
