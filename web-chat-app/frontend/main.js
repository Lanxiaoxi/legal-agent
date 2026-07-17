// Configuration
const CONFIG = {
  API_URL: '/api/chat',
  MAX_MESSAGE_LENGTH: 5000,
  MAX_HISTORY_MESSAGES: 100,
  STORAGE_KEY: 'chat_sessions',
  MAX_RETRIES: 3,
  LOADING_DELAY: 200,
  OPTIMISTIC_UPDATE_DELAY: 100,
  MODELS: [
    { value: 'deepseek-v4-flash', label: 'DeepSeek V4 Flash' },
    { value: 'deepseek-v4-pro', label: 'DeepSeek V4 Pro' }
  ]
};

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
  selectedModel: CONFIG.MODELS[0].value,
  hasSession: true        // Track if there is an active session
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
      
      // If no sessions, create a default one
      if (Object.keys(state.sessions).length === 0) {
        createNewSession();
      }
    } else {
      createNewSession();
    }
    renderMessages();
  } catch (e) {
    console.error('Failed to load sessions:', e);
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
      currentSessionId: state.currentSessionId
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
    model: state.selectedModel
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
    saveHistory();
    render();
    scrollToBottom();
  }
}

// Delete a session
function deleteSession(sessionId) {
  const wasCurrentSession = state.currentSessionId === sessionId;
  
  delete state.sessions[sessionId];
  
  // If no sessions left, switch to empty state (user creates new manually)
  if (Object.keys(state.sessions).length === 0) {
    state.currentSessionId = null;
    state.hasSession = false;
  } else if (wasCurrentSession) {
    // If deleted current session, switch to another
    const remainingIds = Object.keys(state.sessions);
    state.currentSessionId = remainingIds[0];
    state.selectedModel = state.sessions[remainingIds[0]].model || CONFIG.MODELS[0].value;
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
  } else if (e.target.classList.contains('session-item')) {
    const sessionId = e.target.dataset.sessionId;
    switchSession(sessionId);
  } else if (e.target.classList.contains('delete-session-btn')) {
    const sessionId = e.target.closest('.session-item').dataset.sessionId;
    deleteSession(sessionId);
  }
}

// Handle change events
function handleChange(e) {
  if (e.target.classList.contains('model-select')) {
    state.selectedModel = e.target.value;
  }
}

// Handle key press events
function handleKeyPress(e) {
  if (e.target.tagName === 'INPUT' && e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    sendMessage();
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
    setError(validation.error);
    return;
  }

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
    timestamp: Date.now()
  };

  // Add AI message placeholder after user message
  session.messages.push(aiMessage);
  state.currentStreamingId = aiMessage.id;
  state.currentStreamingContent = '';
  state.isStreaming = true;
  renderMessages();
  scrollToBottom();

  try {
    const history = session.messages
      .filter(m => m.id !== state.currentStreamingId)
      .slice(-20)
      .map(m => ({ role: m.role, content: m.content }));

    const response = await fetch(CONFIG.API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history, model: state.selectedModel })
    });

    if (!response.ok) {
      const errorData = await response.json().catch(() => ({}));
      throw new Error(errorData.error || `HTTP ${response.status}`);
    }

    // Handle streaming response
    const reader = response.body.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');

      for (const line of lines) {
        if (line.startsWith('data: ')) {
          try {
            const data = JSON.parse(line.slice(6));
            if (data.content) {
              state.currentStreamingContent += data.content;
              updateStreamingMessage();
            }
            if (data.done) {
              state.isStreaming = false;
              finalizeStreamingMessage();
            }
          } catch (e) {
            // Ignore parse errors for incomplete chunks
          }
        }
      }
    }
  } catch (error) {
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

// Update streaming message content
function updateStreamingMessage() {
  const session = getCurrentSession();
  if (!session) return;
  
  const idx = session.messages.findIndex(m => m.id === state.currentStreamingId);
  if (idx !== -1) {
    session.messages[idx].content = state.currentStreamingContent;
    session.updatedAt = Date.now();
    renderMessages();
    scrollToBottom();
  }
}

// Finalize streaming message
function finalizeStreamingMessage() {
  const session = getCurrentSession();
  if (session) {
    session.updatedAt = Date.now();
  }
  saveHistory();
  renderMessages();
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
    list.scrollTop = list.scrollHeight;
  }
}

// Generate unique ID
function generateId() {
  return 'msg_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
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
          <button class="new-session-btn">+ New Chat</button>
        </div>
        <div class="session-list">
          ${sessionIds.map(id => {
            const s = state.sessions[id];
            const isActive = id === state.currentSessionId;
            return `
              <div class="session-item ${isActive ? 'active' : ''}" data-session-id="${id}">
                <span class="session-title">${escapeHtml(s.title)}</span>
                <button class="delete-session-btn" title="Delete session">×</button>
              </div>
            `;
          }).join('')}
        </div>
      </div>
      <div class="chat-container">
        <div class="chat-header">
          <h1>AI Legal Advisor</h1>
          <div class="header-controls">
            <select class="model-select" ${state.isLoading ? 'disabled' : ''}>
              ${CONFIG.MODELS.map(m => `<option value="${m.value}" ${state.selectedModel === m.value ? 'selected' : ''}>${m.label}</option>`).join('')}
            </select>
          </div>
        </div>
        <div class="message-list"></div>
        ${state.isLoading ? '<div class="loading-indicator">Thinking...</div>' : ''}
        ${state.error ? `<div class="error-message">${escapeHtml(state.error)}</div>` : ''}
        <div class="input-container">
          <input type="text" placeholder="Ask a legal question..." maxlength="${CONFIG.MAX_MESSAGE_LENGTH}" ${state.isLoading || !state.hasSession ? 'disabled' : ''}>
          <button class="send-btn" ${state.isLoading || !state.hasSession ? 'disabled' : ''}>Send</button>
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
          <button class="delete-session-btn" title="Delete session">×</button>
        </div>
      `;
    }).join('');
  }

  elements.messageList.innerHTML = messages.map(msg => `
    <div class="message message-${msg.role}">
      ${escapeHtml(msg.content)}
    </div>
  `).join('');
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

// Start the app
document.addEventListener('DOMContentLoaded', init);