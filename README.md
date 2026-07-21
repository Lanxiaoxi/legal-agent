# AI Legal Advisor

一个基于 DeepSeek API + OpenAI Agents SDK 的法律咨询聊天应用。

## 功能特性

- 🤖 **AI 法律助手** - 回答常见法律问题，基于法律知识库
- 💬 **流式响应** - SSE 实时流式输出，即时获取 AI 回复
- 💾 **多会话支持** - 创建、切换、删除多个对话，会话自动保存到 localStorage
- � **Markdown 支持** - AI 回复内容支持 Markdown 渲染
- �🔄 **模型选择** - 支持 DeepSeek V4 Flash / V4 Pro / Chat / Reasoner
- 🧠 **深度思考** - 可开启/关闭 DeepSeek 推理过程显示
- ⚡ **思考强度** - Low / High / Max 三档推理深度选择
- 🔄 **重试机制** - 网络错误时自动保留输入，支持手动重试
- 🔍 **法律工具** - 内置法律条文查询、关键词搜索、网络搜索功能
- 📱 **响应式设计** - 简洁美观的 UI，支持多种屏幕尺寸

## 支持的模型

- DeepSeek V4 Flash
- DeepSeek V4 Pro
- DeepSeek Chat
- DeepSeek Reasoner

## 思考模式

- **Thinking 开关** - 可开启/关闭 AI 思考过程显示
- **Effort 强度** - Low / High / Max 三档选择，控制推理深度

## 项目架构

```
web-chat-app/
├── backend/
│   ├── main.py          # FastAPI 主应用入口
│   ├── agent.py         # OpenAI Agents SDK Agent 定义
│   ├── config.py        # 配置管理（环境变量 + config.json）
│   ├── config.json      # 配置文件
│   ├── tools.py         # 法律工具函数
│   └── routes/
│       └── chat.py      # 聊天 API 路由（SSE 流式响应）
├── frontend/
│   ├── index.html       # 主页面
│   ├── main.js          # 前端逻辑（原生 JavaScript）
│   └── styles.css       # 样式
├── proxy.py             # 开发代理服务
└── pyproject.toml       # 项目配置
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

3. 安装依赖：
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
   python main.py
   ```
   后端将在 http://localhost:8000 运行

2. 启动前端（任选一种方式）：

   **方式一：直接打开 HTML**
   
   在浏览器中打开 `frontend/index.html`

   **方式二：使用代理服务**
   ```bash
   python proxy.py
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

## 法律工具

应用内置以下工具，AI 会根据问题自动调用：

- **get_legal_reference** - 查询指定类型的法律条文（合同法、物权法、民法典、劳动法、刑法）
- **search_legal_keyword** - 根据关键词搜索相关法律条文（违约金、侵权、租赁、离婚、继承、债务等）
- **web_search** - 使用 Tavily 搜索互联网获取最新信息

## 使用说明

1. **新建对话**: 点击侧边栏的 "+ New Chat" 按钮
2. **切换会话**: 点击侧边栏中的会话列表项
3. **删除会话**: 悬停会话并点击 × 按钮
4. **选择模型**: 在顶部下拉菜单选择模型
5. **调整思考**: 通过 Thinking 开关和 Effort 下拉框控制推理过程显示
6. **清除对话**: 点击 "Clear" 按钮（当前会话）

## 注意事项

⚠️ 本应用提供的仅是法律信息参考，不能替代专业律师的法律意见。如需具体法律帮助，请咨询执业律师。

## 许可证

MIT License