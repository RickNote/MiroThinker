# MiroThinker MCP Server

MiroThinker 的 MCP 服务封装，提供信息搜索、网页抓取、内容整理和系统性研究工具。

## 工具列表

| 工具 | 说明 |
|------|------|
| `miro_search` | 搜索互联网（基于 Serper API） |
| `miro_read` | 阅读网页内容（基于 Jina + LLM 提取） |
| `miro_summarize` | 整理和总结大段信息 |
| `miro_research` | 系统性多轮研究某个话题 |

## 快速开始

### 1. 环境变量配置

复制 `.env.example` 为 `.env` 并填入你的 API Keys：

```bash
cp .env.example .env
# 编辑 .env 填入真实的 API Keys
```

### 2. 本地运行

```bash
pip install -r requirements.txt
python mcp_server.py
```

### 3. 部署到 Railway

1. Fork 这个仓库
2. 在 Railway 中导入项目
3. 配置环境变量（见下方列表）
4. 部署

## 环境变量

| 变量 | 必填 | 默认值 | 说明 |
|------|:----:|--------|------|
| `SERPER_API_KEY` | ✅ | — | Serper Google 搜索 API Key |
| `SERPER_BASE_URL` | ❌ | `https://google.serper.dev` | Serper API 地址 |
| `JINA_API_KEY` | ✅ | — | Jina 网页抓取 API Key |
| `JINA_BASE_URL` | ❌ | `https://r.jina.ai` | Jina API 地址 |
| `LLM_API_KEY` | ✅ | — | 主 LLM API Key |
| `LLM_BASE_URL` | ✅ | — | 主 LLM 地址（OpenAI SDK 格式） |
| `LLM_MODEL` | ✅ | — | 主 LLM 模型名 |
| `SUMMARY_LLM_API_KEY` | ❌ | 复用主 LLM | 摘要 LLM API Key |
| `SUMMARY_LLM_BASE_URL` | ❌ | 复用主 LLM | 摘要 LLM 地址 |
| `SUMMARY_LLM_MODEL` | ❌ | 复用主 LLM | 摘要 LLM 模型名 |
| `PORT` | ❌ | `8000` | 服务端口 |

## LLM 供应商配置

| 提供商 | `LLM_BASE_URL` | `LLM_MODEL` |
|--------|----------------|-------------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-128k` |
| MiniMax | `https://api.minimax.chat/v1` | `MiniMax-Text-01` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |

## Claudian 客户端配置

### MCP 连接配置

```json
{
  "mcpServers": {
    "mirothinker": {
      "type": "sse",
      "url": "https://your-railway-url.up.railway.app/sse"
    }
  }
}
```

### 系统提示

```
当你需要搜索互联网、查证信息或研究某个话题时：
- ✅ 使用 MiroThinker MCP 的 miro_ 系列工具
- ❌ 不要使用内置的 WebSearch 和 WebFetch（当前环境不可用）

工具清单：
- miro_search: 搜索互联网
- miro_read: 读取网页内容
- miro_summarize: 整理总结信息
- miro_research: 系统性研究某个话题（多轮自动搜索和整理）

使用策略由你判断：简单查询用 miro_search，看网页用 miro_read，
整理信息用 miro_summarize，复杂话题用 miro_research。
```

## 许可证

MIT
