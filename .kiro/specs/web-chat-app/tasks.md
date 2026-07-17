# Implementation Plan: web-chat-app

## Overview

This implementation plan covers a full-stack Web Chat Application with a React frontend and Python FastAPI backend. The frontend provides a chat interface for users to interact with an AI legal advisor, while the backend proxies requests to the DeepSeek API with streaming responses.

Key implementation decisions:
- **Frontend**: React with TypeScript, using sessionStorage for conversation persistence
- **Backend**: Python FastAPI with streaming SSE responses
- **No property tests** - The design document explicitly states PBT does not apply to this feature due to UI rendering and external API integration nature

## Tasks

- [ ] 1. Set up project structure and configuration
  - [ ] 1.1 Create frontend project structure (React app with components)
    - Set up React project with TypeScript
    - Create components directory structure (ChatView, MessageList, InputPanel, LoadingIndicator, ClearButton)
    - Configure build tools and dependencies
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6, 1.7_

  - [ ] 1.2 Create backend project structure (Python FastAPI)
    - Set up Python project with FastAPI and dependencies
    - Create API route handlers directory
    - Create configuration module for API key and CORS settings
    - _Requirements: 9.1, 9.2, 9.3, 10.1, 10.2, 10.3, 10.4, 11.1, 11.2, 11.3_

- [ ] 2. Implement backend core components
  - [ ] 2.1 Create FastAPI application with CORS middleware
    - Set up FastAPI app with title "Legal Advisor API"
    - Configure CORS middleware with allow_origins, allow_methods, allow_headers
    - Read CORS_ORIGIN from environment variable or use default "http://localhost:3000"
    - Handle OPTIONS preflight requests
    - _Requirements: 11.1, 11.2, 11.3_

  - [ ] 2.2 Implement /api/chat POST endpoint
    - Create POST /api/chat endpoint accepting JSON with "message" and optional "history"
    - Implement request validation (non-empty message, max 5000 chars)
    - Return appropriate HTTP 400 for invalid requests
    - _Requirements: 9.1, 9.2, 9.3, 9.6, 9.7_

  - [ ] 2.3 Implement request validator
    - Validate JSON is well-formed
    - Validate "message" field exists and is non-empty string
    - Return tuple (is_valid, error_message)
    - _Requirements: 9.6, 9.7_

  - [ ] 2.4 Implement history manager
    - Extract conversation history from request
    - Limit to most recent 20 messages when calling DeepSeek
    - Add system message: "You are a professional legal advisor assistant"
    - _Requirements: 9.3, 9.9_

  - [ ] 2.5 Implement stream proxy to DeepSeek API
    - Forward requests to DeepSeek API (https://api.deepseek.com/v1/chat/completions)
    - Use deepseek-chat model with streaming enabled
    - Stream responses back as SSE data chunks
    - Implement 30-second timeout
    - Handle errors and transform to HTTP 401/502 responses
    - _Requirements: 9.4, 9.5, 9.8, 10.2, 10.4_

  - [ ]* 2.6 Write unit tests for backend components
    - Test request validation (empty, whitespace, missing field)
    - Test history limiting (20 message max)
    - Test error handling (400, 401, 502 responses)
    - _Requirements: 9.6, 9.7, 9.8, 9.9, 10.4_

  - [ ]* 2.7 Write integration tests for backend API
    - Test /api/chat with valid request returns 200
    - Test /api/chat with missing message returns 400
    - Test /api/chat with empty message returns 400
    - Test CORS headers in responses
    - Test OPTIONS preflight request
    - _Requirements: 9.6, 9.7, 11.1, 11.2_

- [ ] 3. Implement frontend core components
  - [ ] 3.1 Create ChatView component (container)
    - Manage overall application state (messages, isLoading, error, retryCount)
    - Render MessageList, InputPanel, LoadingIndicator, ClearButton
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_

  - [ ] 3.2 Create MessageList component
    - Display all messages in chronological order (oldest first)
    - User messages: right-aligned, distinct color
    - AI messages: left-aligned, different color
    - Manage 100-message limit (remove oldest when exceeded)
    - Render streaming content incrementally
    - _Requirements: 1.1, 1.2, 3.2, 3.3, 7.1, 7.2, 7.4_

  - [ ] 3.3 Create InputPanel component
    - Text input field (max 5000 characters)
    - Send button
    - Handle Enter key press to send
    - Disable during loading or when disconnected
    - Validate non-empty and non-whitespace-only input
    - Preserve input on error for retry
    - _Requirements: 1.3, 1.4, 1.5, 1.7, 2.1, 2.2, 2.4, 6.3_

  - [ ] 3.4 Create LoadingIndicator component
    - Display visible loading state
    - Show within 200ms of sending request
    - Hide when streaming completes or error occurs
    - _Requirements: 5.1, 5.2, 5.3_

  - [ ] 3.5 Create ClearButton component
    - Clear all messages and reset conversation
    - Clear sessionStorage on click
    - _Requirements: 8.1, 8.2_

- [ ] 4. Implement frontend state management and API integration
  - [ ] 4.1 Implement conversation history with sessionStorage
    - Store messages in sessionStorage under "chat_history" key
    - Load history on app initialization
    - Save after each message send
    - Limit to 100 messages (remove oldest when exceeded)
    - _Requirements: 7.3, 7.4_

  - [ ] 4.2 Implement message sending with streaming
    - Send POST request to /api/chat with message and history
    - Display user message immediately (within 100ms)
    - Clear input field after send
    - Create AI message placeholder when first chunk received
    - Append subsequent chunks to existing message
    - Finalize message when done=true received
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 4.4_

  - [ ] 4.3 Implement error handling and retry logic
    - Display error message on failure (network, API error)
    - Preserve user's input data on error
    - Show retry control
    - Implement max 3 retry attempts with exponential backoff
    - After max retries, prompt user to refresh page
    - _Requirements: 2.5, 2.6, 6.1, 6.2, 6.3, 6.4_

  - [ ]* 4.4 Write unit tests for frontend components
    - Test InputPanel validation (empty, whitespace, max length)
    - Test MessageList message limit (100 messages)
    - Test error state and retry count
    - _Requirements: 2.5, 6.3, 7.4_

  - [ ]* 4.5 Write integration tests for frontend API
    - Test successful message send and response display
    - Test error handling for failed requests
    - Test streaming behavior
    - _Requirements: 2.5, 3.1, 4.1, 4.2, 4.3, 4.4, 4.5_

- [ ] 5. Checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [ ] 6. Polish and final integration
  - [ ] 6.1 Add styling to chat interface
    - User messages: right-aligned, blue/green background
    - AI messages: left-aligned, gray background
    - Responsive layout
    - _Requirements: 3.2_

  - [ ] 6.2 Verify connection state handling
    - Disable input and send button when disconnected
    - Display appropriate UI state
    - _Requirements: 1.7_

  - [ ]* 6.3 Write E2E tests for complete flows
    - Test complete chat flow (send message → receive response)
    - Test streaming behavior
    - Test error handling and retry
    - Test clear conversation
    - _Requirements: 2.1, 2.2, 2.5, 3.1, 4.1, 4.4, 8.1, 8.2_

- [ ] 7. Final checkpoint - Ensure all tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Tasks marked with `*` are optional and can be skipped for faster MVP
- Each task references specific requirements for traceability
- No property tests - design explicitly states PBT does not apply
- Unit tests and integration tests validate core functionality
- E2E tests validate complete user flows
- Backend uses Python FastAPI; frontend uses React with TypeScript
- Streaming uses Server-Sent Events (SSE) format

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.2"] },
    { "id": 1, "tasks": ["2.1", "2.2", "3.1"] },
    { "id": 2, "tasks": ["2.3", "2.4", "2.5", "3.2", "3.3", "3.4", "3.5"] },
    { "id": 3, "tasks": ["4.1", "4.2", "4.3"] },
    { "id": 4, "tasks": ["2.6", "2.7", "4.4", "4.5"] },
    { "id": 5, "tasks": ["6.1", "6.2"] },
    { "id": 6, "tasks": ["6.3"] }
  ]
}
```