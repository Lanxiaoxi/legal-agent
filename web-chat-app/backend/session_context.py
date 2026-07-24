"""Session 上下文模块 - 通过 contextvars 在请求链路中传递 session_id"""
import contextvars

# 当前请求的 session_id，由 chat 路由在收到请求时设置
current_session_id: contextvars.ContextVar = contextvars.ContextVar(
    'current_session_id', default=None
)
