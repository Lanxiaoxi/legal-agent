// Configuration
const CONFIG = {
  API_URL: '/api/chat',
  MAX_MESSAGE_LENGTH: 5000,
  MAX_HISTORY_MESSAGES: 100,
  STORAGE_KEY: 'chat_history',
  MAX_RETRIES: 3,
  LOADING_DELAY: 200,
  OPTIMISTIC_UPDATE_DELAY: 100
};

// State
let state = {
  messages: [],
  isLoading: false,
  error: null,
  retryCount: 0,
  preservedInput: '',
  isStreaming: false,
  currentStreamingContent: '',
  currentStreamingId: null
};

// DOM Elements
const elements = {};

// Initialize app
function init() {
  render();
  loadHistory();
  setupEventListeners();
}

// Load conversation history from sessionStorage
function loadHistory() {
  try {
    const stored = sessionStorage.getItem(CONFIG.STORAGE_KEY);
    if (stored) {
      state.messages = JSON.parse(stored);
      renderMessages();
    }
  } catch (e) {
    console.error('Failed to load history:', e);
    state.messages = [];
  }
}

// Save conversation history to sessionStorage
function saveHistory() {
  try {
    // Limit to MAX_HISTORY_MESSAGES
    if (state.messages.length > CONFIG.MAX_HISTORY_MESSAGES) {
      state.messages = state.messages.slice(-CONFIG.MAX_HISTORY_MESSAGES);
    }
    sessionStorage.setItem(CONFIG.STORAGE_KEY, JSON.stringify(state.messages));
  } catch (e) {
    console.error('Failed to save history:', e);
  }
}

// Setup event listeners
function setupEventListeners() {
  document.addEventListener('click', handleClick);
  document.addEventListener('keypress', handleKeyPress);
}

// Handle click events
function handleClick(e) {
  if (e.target.classList.contains('send-btn')) {
    sendMessage();
  } else if (e.target.classList.contains('clear-btn')) {
    clearConversation();
  } else if (e.target.classList.contains('retry-btn')) {
    retryMessage();
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
  if (!input) return;

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

  // Create user message
  const userMessage = {
    id: generateId(),
    role: 'user',
    content: message,
    timestamp: Date.now()
  };

  // Add user message immediately
  state.messages.push(userMessage);
  saveHistory();
  renderMessages();
  scrollToBottom();

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
  state.messages.push(aiMessage);
  state.currentStreamingId = aiMessage.id;
  state.currentStreamingContent = '';
  state.isStreaming = true;
  renderMessages();
  scrollToBottom();

  try {
    const history = state.messages
      .filter(m => m.id !== state.currentStreamingId)
      .slice(-20)
      .map(m => ({ role: m.role, content: m.content }));

    const response = await fetch(CONFIG.API_URL, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message, history })
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
  const idx = state.messages.findIndex(m => m.id === state.currentStreamingId);
  if (idx !== -1) {
    state.messages[idx].content = state.currentStreamingContent;
    renderMessages();
    scrollToBottom();
  }
}

// Finalize streaming message
function finalizeStreamingMessage() {
  saveHistory();
  renderMessages();
}

// Retry failed message
async function retryMessage() {
  if (state.retryCount >= CONFIG.MAX_RETRIES) {
    setError('Maximum retry attempts exceeded. Please refresh the page.');
    return;
  }

  state.retryCount++;
  const lastUserMessage = state.messages.filter(m => m.role === 'user').pop();
  
  if (lastUserMessage) {
    // Remove the failed AI response
    state.messages = state.messages.filter(m => m.role === 'user');
    elements.input.value = state.preservedInput || lastUserMessage.content;
    state.preservedInput = '';
    setError(null);
    await sendMessage();
  }
}

// Handle errors
function handleError(error) {
  // Remove failed AI message
  state.messages = state.messages.filter(m => m.id !== state.currentStreamingId);
  
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

// Clear conversation
function clearConversation() {
  state.messages = [];
  state.error = null;
  state.retryCount = 0;
  state.preservedInput = '';
  sessionStorage.removeItem(CONFIG.STORAGE_KEY);
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

  app.innerHTML = `
    <div class="chat-container">
      <div class="chat-header">
        <h1>AI Legal Advisor</h1>
        <button class="clear-btn">Clear Conversation</button>
      </div>
      <div class="message-list"></div>
      ${state.isLoading ? '<div class="loading-indicator">Thinking...</div>' : ''}
      ${state.error ? `<div class="error-message">${escapeHtml(state.error)}</div>` : ''}
      <div class="input-container">
        <input type="text" placeholder="Ask a legal question..." maxlength="${CONFIG.MAX_MESSAGE_LENGTH}" ${state.isLoading ? 'disabled' : ''}>
        <button class="send-btn" ${state.isLoading ? 'disabled' : ''}>Send</button>
      </div>
      ${state.retryCount > 0 && state.error ? '<div style="padding: 0 20px 16px;"><button class="retry-btn">Retry</button></div>' : ''}
    `;

  // Cache DOM elements
  elements.input = document.querySelector('.input-container input');
  elements.messageList = document.querySelector('.message-list');

  renderMessages();
}

// Render messages
function renderMessages() {
  if (!elements.messageList) return;

  elements.messageList.innerHTML = state.messages.map(msg => `
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