# AI Legal Advisor

一个基于 DeepSeek API + OpenAI Agents SDK 的法律咨询聊天应用。

## 功能特性

- 🤖 AI 法律助手 - 回答常见法律问题，基于法律知识库
- 💬 流式响应 - 即时获取 AI 回复
- 💾 多会话支持 - 创建、切换、删除多个对话
- 📝 持久化存储 - 自动保存会话到 localStorage
- 🔄 模型选择 - 支持选择不同的 DeepSeek 模型
- 🧠 深度思考 - 可开启 DeepSeek 推理过程
- 🔄 重试机制 - 网络错误时自动重试
- 🔍 法律工具 - 内置法律条文查询、网络搜索功能

## 支持的模型

- DeepSeek V4 Flash
- DeepSeek V4 Pro
- DeepSeek Chat
- DeepSeek Reasoner

## 思考模式

- **思考开关** - 可开启/关闭 AI 思考过程显示
- **思考强度** - Low / High / Max 三档选择

## 快速开始

### 前置要求

- Python 3.10+
- DeepSeek API Key

### 安装配置

1. 克隆项目并进入目录：
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
| tavilyApiKey | TAVILY_API_KEY | - | Tavily 搜索 API 密钥（可选，用于网络搜索功能） |

## 项目结构

```
web-chat-app/
├── backend/
│   ├── main.py        # FastAPI 后端
│   └── config.json    # 配置文件
├── frontend/
│   ├── index.html     # 主页面
│   ├── main.js        # 前端逻辑
│   └── styles.css     # 样式
├── proxy.py           # 代理服务
└── pyproject.toml     # 项目配置
```

## 注意事项

⚠️ 本应用提供的仅是法律信息参考，不能替代专业律师的法律意见。如需具体法律帮助，请咨询执业律师。

## 许可证

MIT License