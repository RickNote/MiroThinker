import asyncio
import logging
from typing import Any, List, Dict, Set

from mcp_config import Config
from llm_client import LLMClient
from mcp_tools.miro_search import _raw_search
from mcp_tools.miro_read import do_miro_read

logger = logging.getLogger("mirothinker")

RESEARCH_PLAN_PROMPT = """你是一个研究助手。用户想研究以下话题：

研究话题: {question}

请规划一系列搜索查询来帮助研究这个话题。请以 JSON 格式返回搜索查询列表，格式如下：
{{
  "search_queries": [
    "第一个搜索查询",
    "第二个搜索查询",
    "第三个搜索查询",
    "第四个搜索查询",
    "第五个搜索查询"
  ]
}}

最多返回 5 个搜索查询，要从不同角度覆盖这个话题。"""

ANALYZE_RESULTS_PROMPT = """你是一个研究助手。我们正在研究以下话题：

研究话题: {question}

已收集的信息摘要:
{findings_summary}

请分析这些信息，从以下维度评估：
1. 当前信息覆盖了哪些方面？（技术、商业、监管、案例等）
2. 还缺少哪些关键方面？
3. 已有信息之间是否有矛盾需要验证？
4. 请生成针对具体缺失方面的补充搜索词
5. 如果有特别有价值但摘要太短的 URL，请建议深入阅读

请以 JSON 格式返回：
{{
  "is_sufficient": true/false,
  "confidence": 0-100,
  "covered_aspects": ["已覆盖的方面1", "方面2"],
  "missing_aspects": ["缺失的方面1", "方面2"],
  "contradictions": ["矛盾点1"],
  "further_search_queries": ["针对缺失方面的搜索词1", "搜索词2", "搜索词3"],
  "urls_to_deep_read": ["需要深入阅读的URL1"]
}}

只返回 JSON，不要其他内容。"""

SYNTHESIZE_PROMPT = """你是一个研究助手。请综合以下研究结果：

研究话题: {question}

收集到的信息:
{all_info}

请整理一个清晰的研究总结，格式请参考：
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
    max_rounds: int = 5,
    ctx: Any = None,
) -> str:
    if ctx:
        ctx.info(f"[MiroThinker] 🔬 开始系统性研究: {question}")
        ctx.report_progress(0, max_rounds)
        ctx.info("[MiroThinker] 🧠 正在分析研究问题...")

    all_findings: List[Dict] = []
    all_sources: List[Dict] = []
    visited_urls: Set[str] = set()
    search_count = 0
    read_count = 0
    search_queries_used: List[str] = []

    for round_num in range(max_rounds):
        if ctx:
            ctx.info(f"[MiroThinker] 🔄 研究轮次 {round_num + 1}/{max_rounds}")
            ctx.report_progress(round_num + 1, max_rounds)

        urls_to_deep_read = []

        if round_num == 0:
            plan_result = await llm_client.chat_json(
                RESEARCH_PLAN_PROMPT.format(question=question),
                role="main",
                temperature=0.7,
            )
            search_queries = plan_result.get("search_queries", [question])
            if ctx:
                ctx.info(f"[MiroThinker] 📋 研究计划: 将搜索 {len(search_queries)} 个关键词")
        else:
            findings_list = []
            for f in all_findings[:15]:
                finding = f.get("finding", "")
                if len(finding) > 200:
                    finding = finding[:200] + "..."
                findings_list.append(f"- {finding}")
            findings_summary = "\n".join(findings_list)

            if ctx:
                ctx.info(f"[MiroThinker] 🤔 正在评估已收集的 {len(all_findings)} 条信息...")

            analyze_result = await llm_client.chat_json(
                ANALYZE_RESULTS_PROMPT.format(
                    question=question, findings_summary=findings_summary
                ),
                role="main",
                temperature=0.7,
            )

            if analyze_result.get("is_sufficient", False):
                confidence = analyze_result.get("confidence", 0)
                if confidence >= 70:
                    if ctx:
                        ctx.info(f"[MiroThinker] ✅ 信息已充分({confidence}%)，提前结束研究")
                    break

            if ctx:
                missing = analyze_result.get("missing_aspects", [])
                if missing:
                    ctx.info(f"[MiroThinker] 📊 缺少: {', '.join(missing)}")

            search_queries = analyze_result.get("further_search_queries", [f"{question} 补充信息"])
            urls_to_deep_read = analyze_result.get("urls_to_deep_read", [])

        for url in urls_to_deep_read:
            if url in visited_urls:
                continue
            visited_urls.add(url)
            read_count += 1
            try:
                if ctx:
                    ctx.info(f"[MiroThinker] 📖 深入阅读: {url}")
                read_result = await do_miro_read(
                    config, llm_client, url, query=question, ctx=ctx
                )
                title = url
                all_sources.append({"url": url, "title": title, "content": read_result})
                content_preview = read_result[:300].replace("\n", " ")
                all_findings.append({
                    "finding": content_preview,
                    "source_url": url
                })
            except Exception as e:
                logger.warning(f"Failed to deep read {url}: {e}")
                continue

        for query in search_queries[:3]:
            search_count += 1
            search_queries_used.append(query)

            search_results = await _raw_search(config, query, num_results=5, ctx=ctx)

            urls_to_read = []
            for item in search_results:
                url = item.get("link", "")
                if url and url not in visited_urls:
                    urls_to_read.append(url)

            for url in urls_to_read[:3]:
                if url in visited_urls:
                    continue
                visited_urls.add(url)
                read_count += 1

                try:
                    read_result = await do_miro_read(
                        config, llm_client, url, query=question, ctx=ctx
                    )
                    title = next((item.get("title", url) for item in search_results if item.get("link") == url), url)
                    all_sources.append({"url": url, "title": title, "content": read_result})

                    content_preview = read_result[:300].replace("\n", " ")
                    all_findings.append({
                        "finding": content_preview,
                        "source_url": url
                    })
                except Exception as e:
                    logger.warning(f"Failed to read {url}: {e}")
                    continue

        await asyncio.sleep(1)

    if ctx:
        ctx.info("[MiroThinker] 📊 正在综合研究结果...")

    all_info_text = "\n\n".join(
        [f"来源 {i+1}: {s.get('title', s['url'])}\n{s['content']}" for i, s in enumerate(all_sources)]
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
- 搜索轮数: {min(round_num + 1, max_rounds)}
- 搜索关键词: {search_count} 个
- 访问网页: {read_count} 个
- 有效信息源: {len(all_sources)} 个

### 信息来源
"""
    for i, s in enumerate(all_sources, 1):
        stats_section += f"{i}. [{s.get('title', s['url'])}]({s['url']})\n"

    if ctx:
        ctx.report_progress(max_rounds, max_rounds)
        ctx.info("[MiroThinker] ✅ 研究完成")

    return f"## 调查结果: {question}\n\n{final_summary}\n{stats_section}"
