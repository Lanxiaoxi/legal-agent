// Configuration
const CONFIG = {
  API_URL: '/api/chat',
  UPLOAD_URL: '/api/upload',
  FILES_URL: '/api/files',
  MAX_MESSAGE_LENGTH: 5000,
  MAX_HISTORY_MESSAGES: 100,
  STORAGE_KEY: 'chat_sessions',
  MAX_RETRIES: 3,
  LOADING_DELAY: 200,
  OPTIMISTIC_UPDATE_DELAY: 100,
  ALLOWED_FILE_TYPES: ['.txt', '.pdf', '.docx'],
  MAX_FILE_SIZE_MB: 20,
  MODELS: [
    { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
    { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' }
  ],
};

// LineBreakTransformer: 将连续流按行分割
class LineBreakTransformer {
  constructor() {
    this.buffer = '';
  }

  transform(chunk, controller) {
    this.buffer += chunk;
    const lines = this.buffer.split('\n');
    this.buffer = lines.pop() || '';

    for (const line of lines) {
      if (line.trim()) {
        controller.enqueue(line);
      }
    }
  }

  flush(controller) {
    if (this.buffer) {
      controller.enqueue(this.buffer);
    }
  }
}

// State
let state = {
  sessions: {},           // { sessionId: { id, title, messages: [], createdAt, updatedAt, model } }
  currentSessionId: null,
  isLoading: false,
  error: null,
  retryCount: 0,
  preservedInput: '',
  isStreaming: false,
  currentStreamingContent: '',
  currentStreamingId: null,
  responseTimeInterval: null,  // 定时器ID
  showResponseTime: false,     // 是否开始显示耗时
  selectedModel: CONFIG.MODELS[0].value,
  enableWebSearch: true,   // 是否启用联网搜索
  hasSession: true,        // Track if there is an active session
  uploadedFiles: []         // Current session uploaded files: [{id, name, type, size, chunk_count, created_at}]
};

// Current session convenience getter
function getCurrentSession() {
  return state.currentSessionId ? state.sessions[state.currentSessionId] : null;
}

// DOM Elements
const elements = {};

// Initialize app
function init() {
  render();
  loadHistory();
  setupEventListeners();
  // Restore file list for current session
  if (state.currentSessionId) {
    restoreFileList(state.currentSessionId);
  }
}

// Load all sessions from localStorage
function loadHistory() {
  try {
    const stored = localStorage.getItem(CONFIG.STORAGE_KEY);
    if (stored) {
      const data = JSON.parse(stored);
      state.sessions = data.sessions || {};
      state.currentSessionId = data.currentSessionId || null;
      state.hasSession = Object.keys(state.sessions).length > 0;
      console.log('[INFO] Loaded sessions from storage:', Object.keys(state.sessions).length);
      
      // Load current session settings
      if (state.currentSessionId && state.sessions[state.currentSessionId]) {
        state.selectedModel = state.sessions[state.currentSessionId].model || CONFIG.MODELS[0].value;
      }
      
      // If no sessions, create a default one
      if (Object.keys(state.sessions).length === 0) {
        createNewSession();
      }
    } else {
      console.log('[INFO] No stored sessions, creating default');
      createNewSession();
    }
    renderMessages();
  } catch (e) {
    console.error('[ERROR] Failed to load sessions:', e);
    state.sessions = {};
    state.hasSession = false;
    createNewSession();
  }
}

// Save all sessions to localStorage
function saveHistory() {
  try {
    // Limit each session's messages
    for (const sessionId in state.sessions) {
      const session = state.sessions[sessionId];
      if (session.messages.length > CONFIG.MAX_HISTORY_MESSAGES) {
        session.messages = session.messages.slice(-CONFIG.MAX_HISTORY_MESSAGES);
      }
    }
    
    localStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify({
      sessions: state.sessions,
      currentSessionId: state.currentSessionId,
      selectedModel: state.selectedModel
    }));
  } catch (e) {
    console.error('Failed to save sessions:', e);
  }
}

// Create a new session
function createNewSession() {
  const sessionId = generateId();
  state.sessions[sessionId] = {
    id: sessionId,
    title: 'New Conversation',
    messages: [],
    createdAt: Date.now(),
    updatedAt: Date.now(),
    model: state.selectedModel,
  };
  state.currentSessionId = sessionId;
  state.hasSession = true;
  saveHistory();
  return sessionId;
}

// Switch to a different session
function switchSession(sessionId) {
  if (state.sessions[sessionId]) {
    state.currentSessionId = sessionId;
    state.selectedModel = state.sessions[sessionId].model || CONFIG.MODELS[0].value;
    state.error = null;
    // Restore file list for this session
    restoreFileList(sessionId);
    saveHistory();
    render();
    scrollToBottom();
  }
}

// Delete a session
function deleteSession(sessionId) {
  const wasCurrentSession = state.currentSessionId === sessionId;
  
  // Fire-and-forget: clean up backend files
  fetch(`${CONFIG.FILES_URL}/${sessionId}`, { method: 'DELETE' }).catch(() => {});

  delete state.sessions[sessionId];

  // If no sessions left, switch to empty state (user creates new manually)
  if (Object.keys(state.sessions).length === 0) {
    state.currentSessionId = null;
    state.uploadedFiles = [];
    state.hasSession = false;
  } else if (wasCurrentSession) {
    // If deleted current session, switch to another and load its settings
    const remainingIds = Object.keys(state.sessions);
    state.currentSessionId = remainingIds[0];
    const newSession = state.sessions[remainingIds[0]];
    state.selectedModel = newSession.model || CONFIG.MODELS[0].value;
  }

  saveHistory();
  render();
}

// Update session title based on first message
function updateSessionTitle(sessionId, firstMessage) {
  const session = state.sessions[sessionId];
  if (session && session.title === 'New Conversation') {
    // Use first 30 characters of first user message as title
    let title = firstMessage.trim().substring(0, 30);
    if (firstMessage.trim().length > 30) {
      title += '...';
    }
    session.title = title || 'New Conversation';
    session.updatedAt = Date.now();
    saveHistory();
  }
}

// Setup event listeners
function setupEventListeners() {
  document.addEventListener('click', handleClick);
  document.addEventListener('keypress', handleKeyPress);
  document.addEventListener('change', handleChange);
  // Drag-and-drop file upload
  document.addEventListener('dragover', (e) => {
    e.preventDefault();
    const inputArea = document.querySelector('.input-area');
    if (inputArea) inputArea.classList.add('drag-over');
  });
  document.addEventListener('dragleave', (e) => {
    e.preventDefault();
    const inputArea = document.querySelector('.input-area');
    if (inputArea) inputArea.classList.remove('drag-over');
  });
  document.addEventListener('drop', (e) => {
    e.preventDefault();
    const inputArea = document.querySelector('.input-area');
    if (inputArea) inputArea.classList.remove('drag-over');
    if (e.dataTransfer.files.length > 0) {
      handleFileUpload(e.dataTransfer.files);
    }
  });
}



// Handle click events
function handleClick(e) {
  if (e.target.classList.contains('send-btn')) {
    sendMessage();
  } else if (e.target.classList.contains('clear-btn')) {
    clearConversation();
  } else if (e.target.classList.contains('retry-btn')) {
    retryMessage();
  } else if (e.target.classList.contains('new-session-btn')) {
    createNewSession();
    render();
    if (elements.input) elements.input.focus();
  } else if (e.target.closest('.session-item')) {
    const sessionItem = e.target.closest('.session-item');
    const sessionId = sessionItem.dataset.sessionId;
    switchSession(sessionId);
  } else if (e.target.classList.contains('delete-session-btn')) {
    const sessionId = e.target.closest('.session-item').dataset.sessionId;
    deleteSession(sessionId);
  } else if (e.target.classList.contains('suggestion-chip')) {
    const text = e.target.textContent.trim();
    if (elements.input) {
      elements.input.value = text;
      sendMessage();
    }
  }
}

// Handle change events
function handleChange(e) {
  if (e.target.classList.contains('model-select')) {
    state.selectedModel = e.target.value;
  } else if (e.target.classList.contains('web-search-toggle')) {
    state.enableWebSearch = e.target.checked;
  }
}

// Handle key press events
function handleKeyPress(e) {
  if (e.target.tagName === 'INPUT' && e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
  }
}

// File upload handling

// Trigger file input click
function triggerFileUpload() {
  const fileInput = document.getElementById('file-upload-input');
  if (fileInput) {
    fileInput.click();
  }
}

// Handle file selection from input or drag-and-drop
async function handleFileUpload(fileList) {
  if (!state.hasSession) return;

  const files = Array.from(fileList);
  if (files.length === 0) return;

  // Validate files
  for (const file of files) {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (!CONFIG.ALLOWED_FILE_TYPES.includes(ext)) {
      setError(`不支持的文件类型: ${file.name}（仅支持 ${CONFIG.ALLOWED_FILE_TYPES.join(', ')}）`);
      return;
    }
    if (file.size > CONFIG.MAX_FILE_SIZE_MB * 1024 * 1024) {
      setError(`文件 ${file.name} 超过 ${CONFIG.MAX_FILE_SIZE_MB}MB 限制`);
      return;
    }
  }

  setError(null);

  for (const file of files) {
    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', state.currentSessionId);

      const response = await fetch(CONFIG.UPLOAD_URL, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `上传失败 (${response.status})`);
      }

      const data = await response.json();
      state.uploadedFiles = data.files || [];
      console.log('[INFO] File uploaded:', file.name, '→', state.uploadedFiles.length, 'files in session');
    } catch (error) {
      console.error('[ERROR] File upload failed:', error);
      setError(`文件上传失败: ${error.message}`);
    }
  }

  render();
}

// Remove file tag (only from UI state, backend files are kept for conversation context)
function removeFileTag(fileId) {
  state.uploadedFiles = state.uploadedFiles.filter(f => f.id !== fileId);
  render();
}

// Render file tags above input
function renderFileTags() {
  if (!state.uploadedFiles || state.uploadedFiles.length === 0) return '';
  return `
    <div class="file-tags">
      ${state.uploadedFiles.map(f => `
        <span class="file-tag" title="${escapeHtml(f.name)} (${formatFileSize(f.size)})">
          <span class="file-tag-icon">${getFileIcon(f.type)}</span>
          <span class="file-tag-name">${escapeHtml(f.name)}</span>
          <span class="file-tag-remove" onclick="event.stopPropagation(); removeFileTag('${f.id}')">×</span>
        </span>
      `).join('')}
    </div>
  `;
}

function getFileIcon(type) {
  const icons = { txt: '📄', pdf: '📑', docx: '📝' };
  return icons[type] || '📎';
}

function formatFileSize(bytes) {
  if (bytes < 1024) return bytes + 'B';
  if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
  return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
}

// Restore file list when switching sessions
async function restoreFileList(sessionId) {
  try {
    const response = await fetch(`${CONFIG.FILES_URL}/${sessionId}`);
    if (response.ok) {
      const data = await response.json();
      state.uploadedFiles = data.files || [];
    } else {
      state.uploadedFiles = [];
    }
  } catch (e) {
    state.uploadedFiles = [];
  }
}

// Validate input
function validateInput(text) {
  const trimmed = text.trim();
  if (!trimmed) return { valid: false, error: 'Message cannot be empty' };
  if (trimmed.length > CONFIG.MAX_MESSAGE_LENGTH) {
    return { valid: false, error: `Message cannot exceed ${CONFIG.MAX_MESSAGE_LENGTH} characters` };
  }
  return { valid: true, error: null };
}

// Send message
async function sendMessage() {
  const input = elements.input;
  if (!input || !state.hasSession) return;

  const session = getCurrentSession();
  if (!session) return;

  const message = input.value;
  const validation = validateInput(message);
  if (!validation.valid) {
    console.log('[WARN] Invalid input:', validation.error);
    setError(validation.error);
    return;
  }

  console.log('[INFO] Sending message, length:', message.length, 'model:', state.selectedModel);

  // Clear error and disable input
  setError(null);
  setLoading(true);
  input.disabled = true;

  // Update session model
  session.model = state.selectedModel;

  // Create user message
  const userMessage = {
    id: generateId(),
    role: 'user',
    content: message,
    timestamp: Date.now()
  };

  // Add user message to current session
  session.messages.push(userMessage);
  saveHistory();
  renderMessages();
  scrollToBottom();

  // Update session title if this is the first message
  updateSessionTitle(session.id, message);

  // Clear input
  input.value = '';

  // Create placeholder for AI response
  const aiMessage = {
    id: generateId(),
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
    startTime: Date.now()  // 记录开始时间，用于计算回答耗时
  };

  // Add AI message placeholder after user message
  session.messages.push(aiMessage);
  state.currentStreamingId = aiMessage.id;
  state.currentStreamingContent = '';
  state.isStreaming = true;
  
  // 重置状态
  state.showResponseTime = false;
  
  // 启动定时器，在后台计时（但不显示），直到收到首个content才开始显示
  state.responseTimeInterval = setInterval(() => {
    if (state.isStreaming) {
      // 只更新内存中的计时，不显示
      const session = getCurrentSession();
      if (session) {
        const msg = session.messages.find(m => m.id === state.currentStreamingId);
        if (msg && msg.startTime) {
          msg.responseTime = Date.now() - msg.startTime;
        }
      }
    }
  }, 500);
  
  // Render immediately to show the AI message placeholder
  renderMessages();
  scrollToBottom();

  try {
    const history = session.messages
      .filter(m => m.id !== state.currentStreamingId)
      .slice(-20)
      .map(m => ({ role: m.role, content: m.content }));

    // Append file reference to message if files exist
    let fullMessage = message;
    if (state.uploadedFiles.length > 0) {
      const fileNames = state.uploadedFiles.map(f => f.name).join('、');
      fullMessage = `[已上传文件: ${fileNames}]\n\n${message}`;
    }

    const response = await fetch(CONFIG.API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: fullMessage,
        history,
        session_id: state.currentSessionId,
        model: state.selectedModel,
        enable_web_search: state.enableWebSearch
      })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      console.error('[ERROR] HTTP error:', response.status, errorData);
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    console.log('[INFO] Response received, starting stream');
    
    // Handle streaming response
    const reader = response.body
      .pipeThrough(new TextDecoderStream())
      .pipeThrough(new TransformStream(new LineBreakTransformer()))
      .getReader();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const line = value;
      if (line.startsWith('data: ')) {
        try {
          const data = JSON.parse(line.slice(6));

          // 添加延迟，方便观察流式输出过程
          await new Promise(r => setTimeout(r, 20));

            // Update content (streamed, append)
            if (data.content !== undefined && data.content !== null) {
              // 首次收到非空内容时，开始显示耗时
              if (!state.showResponseTime && data.content !== '') {
                state.showResponseTime = true;
                updateResponseTime();
              }
              
              state.currentStreamingContent += data.content;
              
              // Update session data
              const currentSession = getCurrentSession();
              if (currentSession) {
                const msg = currentSession.messages.find(m => m.id === state.currentStreamingId);
                if (msg) {
                  msg.content = state.currentStreamingContent;
                }
              }

              // Only update the content div directly, don't re-render entire messages
              const messageEls = document.querySelectorAll('.message-assistant');
              if (messageEls.length > 0) {
                const lastAssistantMsg = messageEls[messageEls.length - 1];
                let contentDiv = lastAssistantMsg.querySelector('.message-content');

                if (!contentDiv) {
                  lastAssistantMsg.innerHTML = '<div class="message-content"></div>';
                  contentDiv = lastAssistantMsg.querySelector('.message-content');
                }

                if (contentDiv) {
                  const renderedMd = window.marked ? window.marked.parse(state.currentStreamingContent) : escapeHtml(state.currentStreamingContent);
                  contentDiv.innerHTML = renderedMd;
                  // Add streaming cursor during active streaming
                  if (state.isStreaming) {
                    contentDiv.classList.add('streaming-cursor');
                  }
                }
              }
              scrollToBottom();
            }
            
            if (data.done) {
              state.isStreaming = false;
              // 实时更新耗时显示
              updateResponseTime();
              finalizeStreamingMessage();
            }
            if (data.error) {
              throw new Error(data.error);
            }
          } catch (e) {
            // Ignore parse errors for incomplete chunks
          }
        }
      }
    } catch (error) {
      // 停止定时器
      if (state.responseTimeInterval) {
        clearInterval(state.responseTimeInterval);
        state.responseTimeInterval = null;
      }
      // 重置显示状态
      state.showResponseTime = false;
      state.isStreaming = false;
      handleError(error);
  } finally {
    setLoading(false);
    input.disabled = false;
    input.focus();
    state.currentStreamingId = null;
    state.currentStreamingContent = '';
  }
}

// Update streaming message content - kept for reference but not used
// Content is now updated directly in the stream handler

// Finalize streaming message
function finalizeStreamingMessage() {
  // 停止定时器
  if (state.responseTimeInterval) {
    clearInterval(state.responseTimeInterval);
    state.responseTimeInterval = null;
  }
  
  // 重置显示状态
  state.showResponseTime = false;
  
  const session = getCurrentSession();
  if (session) {
    // 计算回答耗时
    const msg = session.messages.find(m => m.id === state.currentStreamingId);
    if (msg && msg.startTime) {
      msg.responseTime = Date.now() - msg.startTime;
      delete msg.startTime;  // 清理临时字段
      console.log('[INFO] Response completed, total time:', msg.responseTime, 'ms');
    }
    session.updatedAt = Date.now();
  }
  saveHistory();
  renderMessages();
}

// Update response time display during streaming
function updateResponseTime() {
  // 如果还未开始显示耗时，直接返回
  if (!state.showResponseTime) return;
  
  const session = getCurrentSession();
  if (!session || !state.currentStreamingId) return;
  
  const msg = session.messages.find(m => m.id === state.currentStreamingId);
  if (!msg || !msg.startTime) return;
  
  const responseTime = Date.now() - msg.startTime;
  const seconds = (responseTime / 1000).toFixed(2);
  
  // 直接更新耗时显示元素（在气泡外面）
  const wrapperEls = document.querySelectorAll('.message-wrapper-assistant');
  if (wrapperEls.length > 0) {
    const lastWrapper = wrapperEls[wrapperEls.length - 1];
    let timeEl = lastWrapper.querySelector('.response-time');
    
    if (!timeEl) {
      timeEl = document.createElement('div');
      timeEl.className = 'response-time';
      lastWrapper.appendChild(timeEl);
    }
    
    timeEl.textContent = `Response: ${seconds}s`;
  }
}

// Retry failed message
async function retryMessage() {
  const session = getCurrentSession();
  if (!session) return;
  
  if (state.retryCount >= CONFIG.MAX_RETRIES) {
    setError('Maximum retry attempts exceeded. Please refresh the page.');
    return;
  }

  state.retryCount++;
  const lastUserMessage = session.messages.filter(m => m.role === 'user').pop();
  
  if (lastUserMessage) {
    // Remove the failed AI response
    session.messages = session.messages.filter(m => m.role === 'user');
    elements.input.value = state.preservedInput || lastUserMessage.content;
    state.preservedInput = '';
    setError(null);
    await sendMessage();
  }
}

// Handle errors
function handleError(error) {
  console.error('[ERROR] Chat error:', error.message);
  
  const session = getCurrentSession();
  if (session) {
    // Remove failed AI message
    session.messages = session.messages.filter(m => m.id !== state.currentStreamingId);
  }
  
  const errorMsg = error.message || 'Failed to send message';
  setError(errorMsg);
  
  // Preserve input for retry
  state.preservedInput = elements.input?.value || '';
  state.retryCount = 0;
  
  renderMessages();
}

// Set error message
function setError(message) {
  state.error = message;
  render();
}

// Set loading state
function setLoading(loading) {
  state.isLoading = loading;
  if (loading) {
    setTimeout(() => {
      if (state.isLoading) {
        render();
      }
    }, CONFIG.LOADING_DELAY);
  } else {
    render();
  }
}

// Clear conversation (current session only)
function clearConversation() {
  const session = getCurrentSession();
  if (session) {
    session.messages = [];
    session.title = 'New Conversation';
    session.updatedAt = Date.now();
  }
  state.error = null;
  state.retryCount = 0;
  state.preservedInput = '';
  saveHistory();
  render();
  if (elements.input) {
    elements.input.focus();
  }
}

// Scroll to bottom of message list
function scrollToBottom() {
  const list = elements.messageList;
  if (list) {
    // 同步滚动，避免 renderMessages 的 innerHTML 重置滚动位置
    list.scrollTop = list.scrollHeight;
  }
}

// Generate unique ID
function generateId() {
  return 'msg_' + Date.now() + '_' + Math.random().toString(36).substring(2, 11);
}

// Render the app
function render() {
  const app = document.getElementById('app');
  if (!app) return;

  const session = getCurrentSession();
  const sessionIds = Object.keys(state.sessions);

  app.innerHTML = `
    <div class="app-container">
      <div class="sidebar">
        <div class="sidebar-header">
          <button class="new-session-btn"> New Chat</button>
        </div>
        <div class="session-list">
          ${sessionIds.map(id => {
            const s = state.sessions[id];
            const isActive = id === state.currentSessionId;
            return `
              <div class="session-item ${isActive ? 'active' : ''}" data-session-id="${id}">
                <span class="session-title">${escapeHtml(s.title)}</span>
                <button class="delete-session-btn" title="Delete session" onclick="event.stopPropagation(); deleteSession('${id}')">×</button>
              </div>
            `;
          }).join('')}
        </div>
      </div>
      <div class="chat-container">
        <div class="chat-header">
          <h1>AI Legal Advisor</h1>
          <div class="header-controls">
            <label class="web-search-label" title="启用后可使用互联网搜索最新法律资讯">
              <span class="web-search-label-text">联网搜索</span>
              <label class="toggle-switch">
                <input type="checkbox" class="web-search-toggle" ${state.enableWebSearch ? 'checked' : ''}>
                <span class="toggle-slider"></span>
              </label>
            </label>
            <label class="control-label">
              Model
              <select class="model-select" ${state.isLoading ? 'disabled' : ''}>
                ${CONFIG.MODELS.map(m => `<option value="${m.value}" ${state.selectedModel === m.value ? 'selected' : ''}>${m.label}</option>`).join('')}
              </select>
            </label>
          </div>
        </div>
        <div class="message-list"></div>
        ${state.isStreaming ? '<div class="loading-indicator"><span>Generating</span><span class="typing-dots"><span></span><span></span><span></span></span></div>' : ''}
        ${!state.isStreaming && state.isLoading ? '<div class="loading-indicator"><span>Thinking</span><span class="typing-dots"><span></span><span></span><span></span></span></div>' : ''}
        ${state.error ? `<div class="error-message">${escapeHtml(state.error)}</div>` : ''}
        <div class="input-container">
          <div class="input-area">
            ${state.hasSession ? renderFileTags() : ''}
            <div class="input-row">
              <button class="upload-btn" onclick="triggerFileUpload()" ${state.isLoading || !state.hasSession ? 'disabled' : ''} title="上传文件">📎</button>
              <input type="text" placeholder="Ask a legal question..." maxlength="${CONFIG.MAX_MESSAGE_LENGTH}" ${state.isLoading || !state.hasSession ? 'disabled' : ''}>
              <button class="send-btn" ${state.isLoading || !state.hasSession ? 'disabled' : ''} title="Send"></button>
            </div>
          </div>
          <input type="file" id="file-upload-input" accept="${CONFIG.ALLOWED_FILE_TYPES.join(',')}" onchange="handleFileUpload(this.files)" style="display:none" multiple>
        </div>
        ${!state.hasSession ? '<div class="no-session-message">No session available. Click "+ New Chat" to start a new conversation.</div>' : ''}
        ${state.retryCount > 0 && state.error ? '<div style="padding: 0 20px 16px;"><button class="retry-btn">Retry</button></div>' : ''}
      </div>
    </div>
  `;

  // Cache DOM elements
  elements.input = document.querySelector('.input-container input');
  elements.messageList = document.querySelector('.message-list');

  renderMessages();
}

// Render welcome screen
function renderWelcomeScreen() {
  return `
    <div class="welcome-screen">
      <div class="welcome-icon">⚖️</div>
      <h2>Legal AI Assistant</h2>
      <p>I can help you with Chinese legal questions — ask about civil law, criminal law, labor disputes, contracts, and more. I search legal databases and the web to find relevant answers.</p>
      <div class="welcome-suggestions">
        <span class="suggestion-chip">劳动合同纠纷怎么处理</span>
        <span class="suggestion-chip">工伤认定标准是什么</span>
        <span class="suggestion-chip">合同违约责任有哪些</span>
        <span class="suggestion-chip">民事诉讼法起诉流程</span>
      </div>
    </div>
  `;
}

// Render messages
function renderMessages() {
  if (!elements.messageList) return;

  const session = getCurrentSession();
  const messages = session ? session.messages : [];

  // Also render sidebar sessions if it exists
  const sessionListEl = document.querySelector('.session-list');
  if (sessionListEl) {
    const sessionIds = Object.keys(state.sessions);
    sessionListEl.innerHTML = sessionIds.map(id => {
      const s = state.sessions[id];
      const isActive = id === state.currentSessionId;
      return `
        <div class="session-item ${isActive ? 'active' : ''}" data-session-id="${id}">
          <span class="session-title">${escapeHtml(s.title)}</span>
          <button class="delete-session-btn" title="Delete session" onclick="event.stopPropagation(); deleteSession('${id}')">×</button>
        </div>
      `;
    }).join('');
  }

  // If no messages, show welcome screen
  if (messages.length === 0) {
    elements.messageList.innerHTML = renderWelcomeScreen();
    return;
  }

  elements.messageList.innerHTML = messages.map(msg => {
    const renderedContent = window.marked ? window.marked.parse(msg.content || '') : escapeHtml(msg.content);

    // Response time section
    let responseTimeSection = '';
    if (msg.role === 'assistant' && msg.responseTime !== undefined) {
      const seconds = (msg.responseTime / 1000).toFixed(2);
      responseTimeSection = `<div class="response-time">${seconds}s</div>`;
    }

    // Avatar initials
    const avatarHtml = msg.role === 'user'
      ? '<div class="message-avatar avatar-user">You</div>'
      : '<div class="message-avatar avatar-assistant">AI</div>';

    const bubbleClass = msg.role === 'user' ? 'message-user' : 'message-assistant';
    const rowClass = msg.role === 'user' ? 'message-row-user' : 'message-row-assistant';
    const wrapperClass = msg.role === 'user' ? 'message-wrapper-user' : 'message-wrapper-assistant';

    return `
      <div class="message-wrapper ${wrapperClass}">
        <div class="message-row ${rowClass}">
          ${avatarHtml}
          <div class="message ${bubbleClass}">
            <div class="message-content">${renderedContent}</div>
          </div>
        </div>
        ${responseTimeSection}
      </div>
    `;
  }).join('');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Start the app
document.addEventListener('DOMContentLoaded', init);