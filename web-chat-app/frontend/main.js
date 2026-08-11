// Configuration
const CONFIG = {
  API_URL: '/api/chat',
  UPLOAD_URL: '/api/upload',
  FILES_URL: '/api/files',
  FEEDBACK_URL: '/api/feedback',
  MAX_MESSAGE_LENGTH: 5000,
  MAX_HISTORY_MESSAGES: 100,
  STORAGE_KEY: 'chat_sessions',
  MAX_RETRIES: 3,
  LOADING_DELAY: 200,
  OPTIMISTIC_UPDATE_DELAY: 100,
  ALLOWED_FILE_TYPES: ['.txt', '.pdf', '.docx', '.jpg', '.jpeg', '.png', '.bmp'],
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
  enableWebSearch: false,   // 是否启用联网搜索
  hasSession: true,        // Track if there is an active session
  uploadedFiles: [],        // Current session uploaded files: [{id, name, type, size, chunk_count, created_at, status}]
  isUploading: false,       // Whether file upload is in progress
  feedbackModalOpen: false,  // 意见反馈弹窗是否打开
  feedbackSubmitting: false, // 是否正在提交反馈
  donatePopupOpen: false,    // 打赏浮窗是否打开
};

// Persistent anonymous user ID (stored in localStorage, survives refreshes)
const USER_ID_KEY = 'legal_advisor_user_id';

function getUserId() {
  let userId = localStorage.getItem(USER_ID_KEY);
  if (!userId) {
    userId = 'user_' + Date.now() + '_' + Math.random().toString(36).substring(2, 11);
    localStorage.setItem(USER_ID_KEY, userId);
    console.log('[INFO] New user ID generated:', userId);
  }
  return userId;
}

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
  state.uploadedFiles = [];
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
    if (e.dataTransfer.files.length > 0 && !state.isUploading) {
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
  } else if (e.target.classList.contains('feedback-btn')) {
    showFeedbackModal();
  } else if (e.target.classList.contains('donate-btn') || e.target.closest('.donate-btn')) {
    toggleDonatePopup(e);
  } else if (state.donatePopupOpen && !e.target.closest('.donate-popup') && !e.target.closest('.donate-btn')) {
    closeDonatePopup();
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
  if (!state.hasSession || state.isUploading) return;

  const files = Array.from(fileList);
  if (files.length === 0) return;

  // Validate files
  for (const file of files) {
    const ext = '.' + file.name.split('.').pop().toLowerCase();
    if (ext === '.doc') {
      setError(`${file.name}：暂不支持 .doc 格式，请先用 Word / WPS 将文档另存为 .docx 后再上传`);
      return;
    }
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

  // Create placeholder entries with 'uploading' status for immediate feedback
  const placeholders = files.map((file, i) => ({
    id: `_uploading_${Date.now()}_${i}`,
    name: file.name,
    type: file.name.split('.').pop().toLowerCase(),
    size: file.size,
    status: 'uploading'
  }));

  // Show placeholders immediately
  state.uploadedFiles = [...state.uploadedFiles, ...placeholders];
  state.isUploading = true;
  render();

  // Upload sequentially, updating each entry as it completes
  for (let i = 0; i < files.length; i++) {
    const file = files[i];
    const entry = placeholders[i];

    try {
      const formData = new FormData();
      formData.append('file', file);
      formData.append('session_id', state.currentSessionId);
      formData.append('user_id', getUserId());

      const response = await fetch(CONFIG.UPLOAD_URL, {
        method: 'POST',
        body: formData
      });

      if (!response.ok) {
        const errData = await response.json().catch(() => ({}));
        throw new Error(errData.detail || `上传失败 (${response.status})`);
      }

      const data = await response.json();
      // Server returns all files for this session; mark them as done
      const serverFiles = (data.files || []).map(f => ({ ...f, status: 'done' }));
      // Combine: all server-confirmed files + remaining placeholders
      state.uploadedFiles = [...serverFiles, ...placeholders.slice(i + 1)];
      console.log('[INFO] File uploaded:', file.name, '→', serverFiles.length, 'files in session');
    } catch (error) {
      console.error('[ERROR] File upload failed:', error);
      entry.status = 'error';
      entry.error = error.message;
      // Rebuild: keep successfully uploaded files + this error entry + remaining placeholders
      const doneFiles = state.uploadedFiles.filter(f => f.status === 'done');
      state.uploadedFiles = [...doneFiles, entry, ...placeholders.slice(i + 1)];
    }

    // Re-render after each file to update its status in the UI
    render();
  }

  state.isUploading = false;
  render();
}

// Remove file tag: 真实删除后端文件（分块 + metadata），不只移除 UI
async function removeFileTag(fileId) {
  const sessionId = state.currentSessionId;
  if (!sessionId) return;

  try {
    const response = await fetch(`${CONFIG.FILES_URL}/${sessionId}/${fileId}`, { method: 'DELETE' });
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `删除失败 (${response.status})`);
    }
    // 以后端返回的文件列表为准
    const data = await response.json();
    state.uploadedFiles = (data.files || []).map(f => ({ ...f, status: 'done' }));
  } catch (error) {
    console.error('[ERROR] File delete failed:', error);
    setError(`删除文件失败: ${error.message}`);
  }
  render();
}

// Render file tags above input
function renderFileTags() {
  if (!state.uploadedFiles || state.uploadedFiles.length === 0) return '';
  return `
    <div class="file-tags">
      ${state.uploadedFiles.map(f => {
        const isUploading = f.status === 'uploading';
        const isError = f.status === 'error';
        const isGenerated = f.generated === true;
        const tagClass = isUploading ? 'file-tag file-tag-uploading'
          : isError ? 'file-tag file-tag-error'
          : isGenerated ? 'file-tag file-tag-generated'
          : 'file-tag';
        const title = isError ? `上传失败: ${escapeHtml(f.error || '未知错误')}`
          : isGenerated ? `点击下载: ${escapeHtml(f.name)}`
          : `${escapeHtml(f.name)} (${formatFileSize(f.size)})`;
        const clickAction = isGenerated
          ? ` onclick="event.stopPropagation(); downloadFile('${f.id}')"`
          : '';
        return `
          <span class="${tagClass}" title="${title}"${clickAction}>
            <span class="file-tag-icon">${isUploading ? '<span class="file-spinner"></span>' : isGenerated ? '⬇️' : getFileIcon(f.type)}</span>
            <span class="file-tag-name">${escapeHtml(f.name)}</span>
            ${isUploading ? '' : `<span class="file-tag-remove" onclick="event.stopPropagation(); removeFileTag('${f.id}')">×</span>`}
          </span>
        `;
      }).join('')}
    </div>
  `;
}

// Download an AI-generated document file
async function downloadFile(fileId) {
  const session = getCurrentSession();
  if (!session) return;

  try {
    const response = await fetch(`${CONFIG.FILES_URL}/${session.id}/${fileId}`);
    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `下载失败 (${response.status})`);
    }

    const disposition = response.headers.get('Content-Disposition') || '';
    const nameMatch = disposition.match(/filename\*=UTF-8''([^;]+)|filename="?([^";]+)"?/i);
    let downloadName = 'document.docx';
    if (nameMatch) {
      try {
        downloadName = decodeURIComponent(nameMatch[1] || nameMatch[2] || '');
      } catch (e) {
        downloadName = nameMatch[2] || 'document.docx';
      }
    }

    const blob = await response.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = downloadName;
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
    showToast('已开始下载', 'success');
  } catch (error) {
    console.error('[ERROR] Download failed:', error);
    showToast(`下载失败: ${error.message}`, 'error');
  }
}

function getFileIcon(type) {
  const icons = { txt: '📄', pdf: '📑', docx: '📝', doc: '📝', jpg: '🖼️', jpeg: '🖼️', png: '🖼️', bmp: '🖼️' };
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
      // 竞态保护：异步请求返回时，如果用户已经切换了会话，丢弃结果
      if (state.currentSessionId === sessionId) {
        state.uploadedFiles = data.files || [];
      }
    } else if (state.currentSessionId === sessionId) {
      state.uploadedFiles = [];
    }
  } catch (e) {
    if (state.currentSessionId === sessionId) {
      state.uploadedFiles = [];
    }
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
  const attachedFiles = [...state.uploadedFiles];
  const userMessage = {
    id: generateId(),
    role: 'user',
    content: message,
    timestamp: Date.now(),
    files: attachedFiles.length > 0 ? attachedFiles : undefined
  };

  // Clear file tags from input area — they'll show in the message bubble instead
  if (attachedFiles.length > 0) {
    state.uploadedFiles = [];
  }

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
    if (attachedFiles.length > 0) {
      const fileNames = attachedFiles.map(f => f.name).join('、');
      fullMessage = `[已上传文件: ${fileNames}]\n\n${message}`;
    }

    const response = await fetch(CONFIG.API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: fullMessage,
        history,
        session_id: state.currentSessionId,
        user_id: getUserId(),
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
              // Agent 可能通过工具生成了文档，刷新文件标签区。
              // 捕获当前 sessionId，await 后校验一致性，避免用户已切换会话时误刷新
              const doneSessionId = state.currentSessionId;
              await restoreFileList(doneSessionId);
              if (state.currentSessionId === doneSessionId) {
                render();
              }
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
          <h1>AI 法律专家助手</h1>
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
            <button class="feedback-btn" title="意见反馈">💬 反馈</button>
            <button class="donate-btn" title="打赏支持">☕ 打赏</button>
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
              <button class="upload-btn" onclick="triggerFileUpload()" ${state.isLoading || state.isUploading || !state.hasSession ? 'disabled' : ''} title="上传文件">📎</button>
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
      <p>我可以帮你解答中国法律问题——涵盖民法、刑法、劳动纠纷、合同等领域。</p>
      <div class="welcome-categories">
        <div class="welcome-category">
          <div class="category-header">
            <span class="category-icon">📋</span>
            <span class="category-title">查法条</span>
          </div>
          <div class="category-chips">
            <span class="suggestion-chip">《民法典》合同编有哪些规定</span>
            <span class="suggestion-chip">《劳动合同法》关于解除合同的规定</span>
            <span class="suggestion-chip">《刑法》中关于经济犯罪的条文</span>
          </div>
        </div>
        <div class="welcome-category">
          <div class="category-header">
            <span class="category-icon">💬</span>
            <span class="category-title">问一问</span>
          </div>
          <div class="category-chips">
            <span class="suggestion-chip">劳动合同纠纷怎么维权</span>
            <span class="suggestion-chip">工伤认定标准是什么，怎么申请赔付</span>
            <span class="suggestion-chip">合同违约会承担什么责任</span>
            <span class="suggestion-chip">民事诉讼法起诉应该怎么做</span>
          </div>
        </div>
        <div class="welcome-category">
          <div class="category-header">
            <span class="category-icon">📝</span>
            <span class="category-title">改文档</span>
          </div>
          <div class="category-chips">
            <span class="suggestion-chip">帮我审阅这份文件的错漏</span>
            <span class="suggestion-chip">起草一份借贷协议</span>
            <span class="suggestion-chip">帮我完善这份劳动合同</span>
          </div>
        </div>
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

    // File attachments for user messages
    let filesSection = '';
    if (msg.role === 'user' && msg.files && msg.files.length > 0) {
      filesSection = `
        <div class="message-files">
          ${msg.files.map(f => `
            <span class="message-file-tag">
              <span class="message-file-icon">${getFileIcon(f.type)}</span>
              <span class="message-file-name">${escapeHtml(f.name)}</span>
            </span>
          `).join('')}
        </div>
      `;
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
            ${filesSection}
            <div class="message-content">${renderedContent}</div>
          </div>
        </div>
        ${responseTimeSection}
      </div>
    `;
  }).join('');
}

// ---- Feedback Modal ----

function createFeedbackModal() {
  const overlay = document.createElement('div');
  overlay.className = 'modal-overlay';
  overlay.innerHTML = `
    <div class="modal-container">
      <div class="modal-header">
        <h3>意见反馈</h3>
        <button class="modal-close-btn">×</button>
      </div>
      <div class="modal-body">
        <textarea
          class="feedback-textarea"
          placeholder="请详细描述您遇到的问题或建议...(什么都可以[吐槽][许愿])"
          maxlength="5000"
          rows="6"
        ></textarea>
      </div>
      <div class="modal-footer">
        <button class="modal-cancel-btn">取消</button>
        <button class="feedback-submit-btn">提交</button>
      </div>
    </div>
  `;
  return overlay;
}

function showFeedbackModal() {
  // Remove existing modal if any
  const existing = document.querySelector('.modal-overlay');
  if (existing) existing.remove();

  state.feedbackModalOpen = true;
  state.feedbackSubmitting = false;

  const modal = createFeedbackModal();
  document.body.appendChild(modal);

  // Bind events
  modal.addEventListener('click', function(e) {
    if (e.target === modal || e.target.classList.contains('modal-close-btn')) {
      hideFeedbackModal();
    }
  });

  const submitBtn = modal.querySelector('.feedback-submit-btn');
  submitBtn.addEventListener('click', submitFeedback);

  const cancelBtn = modal.querySelector('.modal-cancel-btn');
  cancelBtn.addEventListener('click', hideFeedbackModal);

  // Close on Escape
  modal._escHandler = function(e) {
    if (e.key === 'Escape') hideFeedbackModal();
  };
  document.addEventListener('keydown', modal._escHandler);

  // Focus textarea
  setTimeout(() => {
    const textarea = modal.querySelector('.feedback-textarea');
    if (textarea) textarea.focus();
  }, 100);
}

function hideFeedbackModal() {
  state.feedbackModalOpen = false;
  state.feedbackSubmitting = false;

  const modal = document.querySelector('.modal-overlay');
  if (modal) {
    if (modal._escHandler) {
      document.removeEventListener('keydown', modal._escHandler);
    }
    modal.remove();
  }
}

async function submitFeedback() {
  const textarea = document.querySelector('.feedback-textarea');
  const content = textarea ? textarea.value.trim() : '';

  if (!content) {
    showToast('请输入反馈内容', 'error');
    return;
  }

  state.feedbackSubmitting = true;
  const submitBtn = document.querySelector('.feedback-submit-btn');
  const cancelBtn = document.querySelector('.modal-cancel-btn');
  if (textarea) textarea.disabled = true;
  if (submitBtn) { submitBtn.disabled = true; submitBtn.textContent = '提交中...'; }
  if (cancelBtn) cancelBtn.disabled = true;

  try {
    const response = await fetch(CONFIG.FEEDBACK_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content, user_id: getUserId() }),
    });

    if (!response.ok) {
      const errData = await response.json().catch(() => ({}));
      throw new Error(errData.detail || `提交失败 (${response.status})`);
    }

    const data = await response.json();
    console.log('[INFO] Feedback submitted:', data.id);
    hideFeedbackModal();
    showToast(data.message || '感谢您的反馈！', 'success');
  } catch (error) {
    console.error('[ERROR] Feedback submit failed:', error);
    state.feedbackSubmitting = false;
    if (textarea) textarea.disabled = false;
    if (submitBtn) { submitBtn.disabled = false; submitBtn.textContent = '提交'; }
    if (cancelBtn) cancelBtn.disabled = false;
    showToast(`提交失败: ${error.message}`, 'error');
  }
}

// ---- Donate Popup ----

function toggleDonatePopup(e) {
  if (state.donatePopupOpen) {
    closeDonatePopup();
    return;
  }

  // Remove existing popup if any
  const existing = document.querySelector('.donate-popup');
  if (existing) existing.remove();

  const btn = e.target.closest('.donate-btn');
  const popup = document.createElement('div');
  popup.className = 'donate-popup';
  popup.innerHTML = `
    <img src="qrcode.png" alt="打赏二维码" onerror="this.style.display='none';this.nextElementSibling.style.display='block';">
    <div class="donate-placeholder" style="display:none;">
      <div class="donate-placeholder-icon">📷</div>
      <p>请将二维码图片保存为<br><code>frontend/qrcode.png</code></p>
    </div>
    <p class="donate-text">感谢您的支持 ☕</p>
  `;

  // Position below the button
  const btnRect = btn.getBoundingClientRect();
  popup.style.position = 'fixed';
  popup.style.top = (btnRect.bottom + 8) + 'px';
  popup.style.right = (window.innerWidth - btnRect.right) + 'px';

  document.body.appendChild(popup);
  state.donatePopupOpen = true;

  // Prevent immediate close from this click
  popup.addEventListener('click', function(ev) { ev.stopPropagation(); });
}

function closeDonatePopup() {
  state.donatePopupOpen = false;
  const popup = document.querySelector('.donate-popup');
  if (popup) popup.remove();
}

// ---- Toast ----

function showToast(message, type = 'success') {
  // Remove existing toast
  const existingToast = document.querySelector('.toast');
  if (existingToast) existingToast.remove();

  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  toast.textContent = message;
  document.body.appendChild(toast);

  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add('toast-visible');
  });

  // Auto remove
  setTimeout(() => {
    toast.classList.remove('toast-visible');
    setTimeout(() => toast.remove(), 300);
  }, 3000);
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Start the app
document.addEventListener('DOMContentLoaded', init);