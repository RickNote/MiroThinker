# Railway 部署详细指南

---

## 一、部署前准备

### 1.1 准备 API Keys

在开始部署前，请确保你已准备好以下 API Keys：

| 服务 | 获取地址 | 说明 |
|------|---------|------|
| Serper API | https://serper.dev/ | Google 搜索 API |
| Jina API | https://jina.ai/ | 网页抓取 API |
| LLM API | 如 DeepSeek / OpenAI / Kimi 等 | 大模型推理 API |

### 1.2 Fork 或 Clone 项目

确保你的 GitHub 仓库中有 `apps/mcp-server/` 目录及其所有文件。

---

## 二、Railway 项目创建

### 2.1 新建项目

1. 登录 [Railway Dashboard](https://railway.app/dashboard)
2. 点击 **"New Project"**
3. 选择 **"Deploy from GitHub repo"**
4. 选择你的 `MiroThinker` 仓库
5. 点击 **"Deploy Now"**（暂不配置，先创建项目）

---

## 三、Railway 配置（关键步骤）

### 3.1 配置 Root Directory

**这是最关键的一步！**

Railway 默认把仓库根目录作为项目根目录，但我们的代码在 `apps/mcp-server/` 子目录下。

**配置步骤**：

```
Railway Dashboard → 你的 Service → Settings → Source

找到 "Root Directory" 设置项：
  - 如果显示 "Add Root Directory" 链接，点击它
  - 出现输入框后，填入：apps/mcp-server
  - 点击 "Save" 或 "Update"
```

### 3.2 切换 Builder

```
在同一个 Settings → Build 区域：

找到 "Builder" 设置：
  - 当前应该是 "Railpack (Default)"
  - 点击它，切换为：Dockerfile

如果出现 "Dockerfile Path" 输入框：
  - 填入：Dockerfile
  - （因为 Root Directory 已经是 apps/mcp-server，所以相对路径就是根目录下的 Dockerfile）
```

### 3.3 配置环境变量

```
Railway Dashboard → 你的 Service → Variables 标签页

点击 "New Variable" 或 "RAW Editor"，添加以下变量：

SERPER_API_KEY=你的serper真实key
JINA_API_KEY=你的jina真实key
LLM_API_KEY=你的llm真实key
LLM_BASE_URL=https://api.deepseek.com/v1
LLM_MODEL=deepseek-chat

（根据你的 LLM 提供商调整 LLM_BASE_URL 和 LLM_MODEL）
```

**LLM 提供商参考配置**：

| 提供商 | LLM_BASE_URL | LLM_MODEL |
|--------|--------------|-----------|
| DeepSeek | `https://api.deepseek.com/v1` | `deepseek-chat` |
| Kimi | `https://api.moonshot.cn/v1` | `moonshot-v1-128k` |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o` |
| MiniMax | `https://api.minimax.chat/v1` | `MiniMax-Text-01` |

### 3.4 配置健康检查

```
Railway Dashboard → 你的 Service → Settings → Deploy 区域

找到 "Healthcheck Path"：
  - 填入：/health
  - （这是我们在 mcp_server.py 中专门添加的健康检查端点）

Healthcheck Timeout 保持默认 300 即可
```

### 3.5 生成公开域名

```
Railway Dashboard → 你的 Service → Settings → Networking 区域

点击 "Generate Domain"
Railway 会分配一个类似：mirothinker-production.up.railway.app 的域名
```

**保存这个 URL，后面配置 Claudian 时需要用到！**

---

## 四、配置文件确认

### 4.1 检查 railway.toml

确保 `apps/mcp-server/railway.toml` 内容如下：

```toml
[build]
builder = "dockerfile"
dockerfilePath = "Dockerfile"

[deploy]
healthcheckPath = "/health"
healthcheckTimeout = 300
restartPolicyType = "on_failure"
restartPolicyMaxRetries = 3
```

**关键点**：
- `dockerfilePath = "Dockerfile"`（**不是** `"apps/mcp-server/Dockerfile"`）
- `healthcheckPath = "/health"`（**不是** `"/sse"`）

### 4.2 检查 requirements.txt

确保 `apps/mcp-server/requirements.txt` 包含：

```
fastmcp>=2.0.0,<3.0.0
mcp>=1.0.0
openai>=1.78.1
httpx>=0.27.0
python-dotenv>=1.0.0
json-repair>=0.49.0
starlette>=0.36.0
uvicorn>=0.30.0
```

### 4.3 检查 Dockerfile

确保 `apps/mcp-server/Dockerfile` 存在且内容正确。

---

## 五、触发部署

### 5.1 提交代码（如有修改）

如果你修改了任何配置文件，先提交推送到 GitHub：

```bash
git add apps/mcp-server/railway.toml
git commit -m "Update railway config"
git push
```

### 5.2 自动部署

推送到 GitHub 后，Railway 会自动触发重新部署。

你也可以手动触发：

```
Railway Dashboard → 你的 Service → Deployments 标签页
→ 点击 "Redeploy" 或 "New Deployment"
```

---

## 六、部署验证

### 6.1 查看 Build Logs

```
Railway Dashboard → 你的 Service → Deployments 标签页
→ 点击最近的一次部署
→ 查看 "Build Logs"
```

**成功的 Build Logs 应该包含**：

```
[1/1] Healthcheck succeeded!
exporting to docker image format
image push
```

### 6.2 查看 Deploy Logs

在同一个部署页面，查看 "Deploy Logs"：

**成功的 Deploy Logs 应该包含**：

```
Starting Container
INFO:mirothinker:Starting MiroThinker MCP Server on port 8080
INFO:     Started server process [1]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8080
INFO:     100.64.0.2:xxxxx - "GET /health HTTP/1.1" 200 OK
```

**常见 Deploy Logs 错误及解决方案**：

| 错误 | 原因 | 解决方案 |
|------|------|---------|
| `ValueError: SERPER_API_KEY is required` | 环境变量未配置 | 检查 Variables 标签页 |
| `AttributeError: 'FastMCP' object has no attribute 'sse_app'` | 代码版本不对 | 确认用的是直接 mcp SDK 版本 |
| `TypeError: 'NoneType' object is not callable` | handle_sse 没返回 Response | 确认有 `return Response()` |

### 6.3 浏览器验证

在浏览器中访问：

```
https://你的域名.up.railway.app/health
```

**应该返回**：

```json
{"status": "ok"}
```

---

## 七、Claudian 客户端配置

### 7.1 配置 MCP Server

打开 Claudian 的 MCP Servers 设置页面，添加新服务器：

```json
{
  "mcpServers": {
    "miro": {
      "type": "sse",
      "url": "https://你的域名.up.railway.app/sse"
    }
  }
}
```

**关键点**：
- **Service Name** 必须是 `miro`（全小写，**不要**用 `mirothinker` 或 `miro-thinker`）
- URL 结尾必须是 `/sse`

### 7.2 配置系统提示

在 Claudian 的 Settings → System Prompt / Custom Instructions 中添加：

```
当你需要搜索互联网、查证信息或研究某个话题时：
- ✅ 使用 MiroThinker MCP 的 miro_ 系列工具
- ❌ 不要使用内置的 WebSearch 和 WebFetch（当前环境不可用）

工具清单：
- miro_search: 搜索互联网
- miro_read: 读取网页内容
- miro_summarize: 整理总结信息
- miro_research: 系统性研究某个话题

使用策略由你判断：简单查询用 miro_search，看网页用 miro_read，
整理信息用 miro_summarize，复杂话题用 miro_research。
```

### 7.3 测试连接

在 Claudian 的 MCP Servers 设置页面，点击 "Verify" 或 "Test Connection"：

**成功时应该显示**：
```
✅ Connected successfully to MiroThinker v1.x.x

Available Tools (4):
1. miro_search - 搜索互联网...
2. miro_read - 读取网页内容...
3. miro_summarize - 整理和总结大段信息...
4. miro_research - 系统性多轮研究某个话题...
```

---

## 八、对话中使用

### 8.1 启用 MCP

**重要**：Claudian 默认在新对话中**不勾选**任何 MCP 服务器（为了节省 Token）。

**启用方式有两种**：

**方式 1：使用 @ 召唤（推荐）**
```
在输入框直接输入：@mi
然后按回车选择 mirothinker
```

**方式 2：手动勾选**
```
在对话输入框下方，找到插头/插件图标
点击展开，勾选 "miro"
```

### 8.2 测试工具

开一个**新对话**，发送：

```
请列出你当前可用的所有 MCP 工具
```

**应该返回包含 `miro_search`、`miro_read`、`miro_summarize`、`miro_research` 的列表**。

然后测试搜索：

```
请使用 miro_search 搜索 "2026 AI trends"
```

### 8.3 常见使用问题

| 问题 | 原因 | 解决方案 |
|------|------|---------|
| AI 说 "没有找到 miro_search 工具" | 当前对话未启用 MCP | 输入 `@miro` 或手动勾选 |
| `Error: No such tool available` | Service Name 不对 | 确认 Service Name 是 `miro` |
| `-32602` 错误 | SSE 会话断开 | 开一个**全新对话** |
| 工具调用但 Deploy Logs 没反应 | 请求未到达服务端 | 检查 URL 配置是否正确 |

---

## 九、部署配置检查清单

在开始部署前，确认以下所有项：

### 代码配置（本地）

- [ ] `apps/mcp-server/railway.toml` 存在且内容正确
- [ ] `dockerfilePath = "Dockerfile"`（**不是** `"apps/mcp-server/Dockerfile"`）
- [ ] `healthcheckPath = "/health"`（**不是** `"/sse"`）
- [ ] `apps/mcp-server/requirements.txt` 包含 `starlette` 和 `uvicorn`
- [ ] `apps/mcp-server/mcp_server.py` 中的 `handle_sse` 函数有 `return Response()`

### Railway 配置（云端）

- [ ] Root Directory = `apps/mcp-server`
- [ ] Builder = `Dockerfile`
- [ ] Dockerfile Path = `Dockerfile`
- [ ] Variables 中已配置：
  - [ ] `SERPER_API_KEY`
  - [ ] `JINA_API_KEY`
  - [ ] `LLM_API_KEY`
  - [ ] `LLM_BASE_URL`
  - [ ] `LLM_MODEL`
- [ ] Healthcheck Path = `/health`
- [ ] 已生成公开域名

### Claudian 配置（客户端）

- [ ] MCP Server URL = `https://你的域名.up.railway.app/sse`
- [ ] Service Name = `miro`（**不是** `mirothinker`）
- [ ] 已添加系统提示
- [ ] Verify 连接成功

---

## 十、完整部署流程时间线

```
T+0:00  准备 API Keys
T+0:05  配置 Railway Root Directory
T+0:10  配置 Railway Builder
T+0:15  配置环境变量
T+0:20  生成公开域名
T+0:25  提交代码（如需要）
T+0:30  等待 Build（约 2-5 分钟）
T+5:00  等待 Deploy（约 1-2 分钟）
T+7:00  验证健康检查端点
T+7:30  配置 Claudian MCP Server
T+8:00  配置 Claudian 系统提示
T+8:30  测试连接
T+9:00  开新对话，@miro 启用
T+9:30  测试 miro_search
T+10:00 完成！🎉
```

---

## 十一、回滚方案

如果部署失败，可以回滚：

### 11.1 回滚代码

```bash
git log --oneline
git reset --hard <上一个正常的commit>
git push --force
```

### 11.2 回滚 Railway 配置

在 Railway Dashboard 中：
- Settings → Source → 清空 Root Directory
- Settings → Build → Builder 改回 Railpack
- Settings → Deploy → 清空 Healthcheck Path

---

## 十二、参考文档

- [Railway Dockerfile 部署文档](https://docs.railway.app/deploy/dockerfiles)
- [MCP 协议规范](https://modelcontextprotocol.io/)
- [Starlette 文档](https://www.starlette.io/)
- [问题修复文档](./问题修复 v1.md) 到 [问题修复 v14.md](./问题修复 v14.md)

---

**文档版本**: v1.0
**最后更新**: 2026-02-15
