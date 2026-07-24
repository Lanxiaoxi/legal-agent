# AI Legal Advisor

一个基于 DeepSeek API + OpenAI Agents SDK 的法律咨询聊天应用。

## 功能特性

- 🤖 **AI 法律助手** - 回答常见法律问题，基于法律知识库
- 💬 **流式响应** - SSE 实时流式输出，即时获取 AI 回复
- 💾 **多会话支持** - 创建、切换、删除多个对话，会话自动保存到 localStorage
- � **Markdown 支持** - AI 回复内容支持 Markdown 渲染
- �🔄 **模型选择** - 支持 DeepSeek V4 Flash / V4 Pro / Chat / Reasoner
- 🔄 **重试机制** - 网络错误时自动保留输入，支持手动重试
- 🔍 **法律工具** - 内置法律条文查询、关键词搜索、网络搜索、已上传文件检索功能
- 📎 **文件上传** - 支持上传 PDF/DOCX/TXT 文件，AI 自动检索文件内容回答问题
- 🗂️ **文件存储管理** - 服务端按会话存储文件分块，7 天 TTL 自动清理
- 📱 **响应式设计** - 简洁美观的 UI，支持多种屏幕尺寸

## 支持的模型

- DeepSeek V4 Flash
- DeepSeek V4 Pro
- DeepSeek Chat
- DeepSeek Reasoner

## 项目架构

```
web-chat-app/
├── backend/
│   ├── main.py                  # FastAPI 主应用入口
│   ├── agent.py                 # OpenAI Agents SDK Agent 定义
│   ├── config.py                # 配置管理（环境变量 + config.json）
│   ├── config.json              # 配置文件
│   ├── session_context.py       # 请求链路 session_id 上下文（contextvars）
│   ├── routes/
│   │   ├── chat.py              # 聊天 API 路由（SSE 流式响应）
│   │   └── upload.py            # 文件上传/列表/删除 API + TTL 清理任务
│   ├── tools/
│   │   ├── __init__.py          # 工具注册
│   │   ├── query_legal.py       # 法律条文查询（编号/关键词/标签）
│   │   ├── web_search.py        # Tavily 互联网搜索
│   │   ├── fetch_webpage.py     # 网页抓取
│   │   ├── get_current_datetime.py  # 获取当前时间
│   │   └── search_uploaded_file.py  # 已上传文件内容检索
│   └── legal_konwlegde/         # 法律知识库（JSON 格式）
│       ├── legal_docs_index.json    # 法律索引
│       └── *.json               # 各法律的结构化条款数据
├── frontend/
│   ├── index.html               # 主页面
│   ├── main.js                  # 前端逻辑（原生 JavaScript）
│   └── styles.css               # 样式
├── proxy.py                     # 开发代理服务（:3000 → :8000）
└── pyproject.toml               # 项目配置（uv 管理依赖）
```

### 技术栈

- **前端**: 原生 JavaScript (无框架依赖), CSS, HTML
- **后端**: FastAPI (Python async)
- **AI 框架**: OpenAI Agents SDK
- **LLM API**: DeepSeek API

## 快速开始

### 前置要求

- Python 3.10+
- DeepSeek API Key

### 安装配置

1. 进入项目目录：
   ```bash
   cd web-chat-app
   ```

2. 创建虚拟环境：
   ```bash
   python -m venv .venv
   .venv\Scripts\activate  # Windows
   # source .venv/bin/activate  # Linux/Mac
   ```

3. 安装依赖（使用 uv）：
   ```bash
   uv sync
   ```
   或使用 pip：
   ```bash
   pip install -e .
   ```

4. 配置 API Key（选择一种方式）：

   **方式一：环境变量**
   ```bash
   export DEEPSEEK_API_KEY="your-api-key"  # Linux/Mac
   set DEEPSEEK_API_KEY=your-api-key       # Windows
   ```

   **方式二：配置文件**
   
   编辑 `backend/config.json`：
   ```json
   {
     "deepseekApiKey": "your-api-key"
   }
   ```

### 启动服务

1. 启动后端：
   ```bash
   cd backend
   uv run python main.py
   ```
   后端将在 http://localhost:8000 运行

2. 启动前端（通过代理服务）：
   ```bash
   cd web-chat-app
   uv run python proxy.py
   ```
   访问 http://localhost:3000

## 配置选项

可在 `backend/config.json` 或环境变量中配置：

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|----------|--------|------|
| deepseekApiKey | DEEPSEEK_API_KEY | - | DeepSeek API 密钥（必填） |
| corsOrigin | CORS_ORIGIN | http://localhost:3000 | CORS 允许的源 |
| deepseekBaseUrl | DEEPSEEK_BASE_URL | https://api.deepseek.com | API 地址 |
| model | DEEPSEEK_MODEL | deepseek-v4-flash | 默认模型 |
| requestTimeout | REQUEST_TIMEOUT | 30 | 请求超时（秒） |
| maxHistoryMessages | MAX_HISTORY_MESSAGES | 20 | 最大历史消息数 |
| port | PORT | 8000 | 后端端口 |
| tavilyApiKey | TAVILY_API_KEY | - | Tavily 搜索 API 密钥（可选） |
| uploadDir | UPLOAD_DIR | ./uploads | 文件上传存储目录 |
| uploadMaxSizeMb | UPLOAD_MAX_SIZE_MB | 20 | 单文件最大大小（MB） |
| uploadTtlDays | UPLOAD_TTL_DAYS | 7 | 上传文件保留天数（过期自动清理） |

## 法律工具

应用内置以下工具，AI 会根据问题自动调用：

- **query_legal** - 查询指定法律条文（按条款编号/关键词/标签搜索）
- **get_legal_info** - 获取法律文件列表及基本信息
- **search_uploaded_file** - 在用户上传的文件中检索相关内容（合同、协议、判决书等）
- **web_search** - 使用 Tavily 搜索互联网获取最新信息
- **fetch_webpage** - 抓取指定网页内容
- **get_current_datetime** - 获取当前日期时间（用于时效计算）

## 使用说明

1. **新建对话**: 点击侧边栏的 "+ New Chat" 按钮
2. **切换会话**: 点击侧边栏中的会话列表项
3. **删除会话**: 悬停会话并点击 × 按钮（关联的上传文件也会自动清理）
4. **选择模型**: 在顶部下拉菜单选择模型
5. **上传文件**: 点击输入框左侧 📎 按钮或拖拽文件到输入区域，支持 PDF / DOCX / TXT 格式
6. **文件问答**: 上传合同或法律文书后，AI 会自动检索文件内容回答相关问题
7. **清除对话**: 点击 "Clear" 按钮（当前会话）

## API 接口

| 方法 | 路径 | 说明 |
|------|------|------|
| `POST` | `/api/chat` | 聊天接口（SSE 流式），支持 `session_id` 关联上传文件 |
| `POST` | `/api/upload` | 上传文件（multipart: file + session_id） |
| `GET` | `/api/files/{session_id}` | 获取会话的已上传文件列表 |
| `DELETE` | `/api/files/{session_id}` | 清理会话的上传文件 |
| `GET` | `/` | 健康检查 |

## 注意事项

⚠️ 本应用提供的仅是法律信息参考，不能替代专业律师的法律意见。如需具体法律帮助，请咨询执业律师。

## 许可证

MIT License