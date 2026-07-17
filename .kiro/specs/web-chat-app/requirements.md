# Requirements Document

## Introduction

This document specifies the requirements for a Web Chat Application that enables users to interact with an AI legal advisor through a web browser. The application consists of a frontend web interface and a backend API that communicates with the DeepSeek AI service.

## Glossary

- **System**: The complete Web Chat Application including frontend and backend components
- **Frontend**: The web-based user interface displayed in the browser
- **Backend_API**: The Python server that handles client requests and communicates with DeepSeek
- **Message**: A single user query or AI response within a conversation
- **Conversation**: A sequence of messages exchanged in a single chat session
- **Stream**: A continuous flow of data chunks from server to client
- **DeepSeek_API**: The external Large Language Model service provider
- **Chat_History**: The visible list of messages displayed in the interface
- **Input_Field**: The text input area where users type their queries
- **Send_Button**: The control for submitting user messages

## Requirements

### Requirement 1: Display Chat Interface

**User Story:** As a user, I want to see a chat interface so that I can interact with the AI legal advisor.

#### Acceptance Criteria

1. THE Frontend SHALL display a Chat_History area that shows all messages in the current conversation
2. THE Frontend SHALL display a Chat_History area that can accommodate up to 100 messages before oldest messages are removed
3. THE Frontend SHALL display an Input_Field for typing messages
4. THE Frontend SHALL display an Input_Field that accepts up to 5000 characters
5. THE Frontend SHALL display a Send_Button for submitting messages
6. THE Frontend SHALL display a title indicating the AI legal advisor
7. THE Frontend SHALL disable the Input_Field and Send_Button when disconnected from the backend

### Requirement 2: Send User Message

**User Story:** As a user, I want to send my question to the AI, so that I can receive legal advice.

#### Acceptance Criteria

1. WHEN the user clicks the Send_Button, THE Frontend SHALL send the message to the Backend_API
2. WHEN the user presses Enter in the Input_Field, THE Frontend SHALL send the message to Backend_API
3. WHEN a message is sent, THE Frontend SHALL display the user's message in the Chat_History within 100 milliseconds
4. WHEN a message is sent, THE Frontend SHALL clear the Input_Field
5. IF the message send to Backend_API fails, THE Frontend SHALL display an error message indicating the send failure
6. IF Backend_API is unavailable, THE Frontend SHALL display an error message indicating the service is unavailable

### Requirement 3: Display AI Response

**User Story:** as a user, I want to see the AI's response, so that I can receive legal advice.

#### Acceptance Criteria

1. WHEN the Backend_API returns a complete response, THE Frontend SHALL display the AI message in the Chat_History within 2 seconds
2. THE Frontend SHALL distinguish user messages from AI messages visually (e.g., different alignment or color)
3. THE Backend_API response SHALL include message source metadata (user or AI) for each message

### Requirement 4: Stream AI Response

**User Story:** As a user, I want to see the AI response as it is generated, so that I can read the answer incrementally.

#### Acceptance Criteria

1. WHEN the Backend_API sends the first content chunk of a streaming response, THE Frontend SHALL create a new AI message placeholder in the Chat_History
2. WHEN the Backend_API sends a subsequent content chunk, THE Frontend SHALL append the chunk content to the existing AI message
3. WHILE the streaming response is in progress, THE Frontend SHALL append content to the current AI message without creating duplicate messages
4. WHEN the streaming response completes (all chunks received), THE Frontend SHALL finalize the AI message display
5. IF the streaming response ends with an error, THE Frontend SHALL display an error message indicating the streaming failure

### Requirement 5: Show Loading State

**User Story:** As a user, I want to know when the AI is processing my request, so that I am aware the system is working.

#### Acceptance Criteria

1. WHEN the Frontend sends a message to the Backend_API and no response has been received, THE Frontend SHALL display a visible loading indicator within 200 milliseconds
2. WHEN all response chunks have been received from the streaming response (signaling streaming complete per Requirement 4), THE Frontend SHALL hide the loading indicator
3. IF the Backend_API returns an error before the complete response is received, THE Frontend SHALL hide the loading indicator

### Requirement 6: Error Handling

**User Story:** As a user, I want to be informed when something goes wrong, so that I can take appropriate action.

#### Acceptance Criteria

1. IF the Backend_API returns an error, THE Frontend SHALL display an error message to the user indicating that the request failed
2. IF a network failure occurs, THE Frontend SHALL display a descriptive error message indicating the nature of the failure
3. IF an error occurs, THE Frontend SHALL preserve the user's input data and display a retry control that allows the user to resubmit the request
4. IF the user retries after an error, THE System SHALL allow a maximum of 3 retry attempts before requiring the user to refresh the page

### Requirement 7: Conversation History

**User Story:** As a user, I want to see previous messages in the conversation, so that I can review the chat context.

#### Acceptance Criteria

1. WHEN a user sends a message, THE Frontend SHALL add the message to the Chat_History
2. THE Frontend SHALL display all messages from the current conversation session in chronological order with oldest messages displayed first
3. THE Frontend SHALL preserve the conversation history using sessionStorage during the browser session
4. THE Frontend SHALL limit the Chat_History to 100 messages, removing the oldest message when the limit is exceeded

### Requirement 8: Clear Conversation

**User Story:** As a user, I want to start a new conversation, so that I can ask unrelated questions.

#### Acceptance Criteria

1. THE Frontend SHALL provide a visible Clear_Button to reset the conversation
2. WHEN the Clear_Button is clicked, THE Frontend SHALL remove all messages from the Chat_History and clear the conversation history from sessionStorage

### Requirement 9: Backend API Endpoint

**User Story:** As a developer, I need a backend API to handle chat requests, so that the frontend can communicate with the AI service.

#### Acceptance Criteria

1. THE Backend_API SHALL expose a POST endpoint at /api/chat to receive user messages
2. THE Backend_API SHALL accept a JSON body with a "message" field containing the user's input
3. THE Backend_API SHALL accept an optional "history" array containing previous messages for context
4. WHEN receiving a valid request with a message, THE Backend_API SHALL call the DeepSeek_API with the conversation history
5. THE Backend_API SHALL return the AI response as a streaming response to the Frontend
6. IF the request JSON is malformed, THE Backend_API SHALL return HTTP 400 with an error message
7. IF the "message" field is empty or missing, THE Backend_API SHALL return HTTP 400 with an error message
8. IF the DeepSeek_API call fails or times out after 30 seconds, THE Backend_API SHALL return HTTP 502 with an error message
9. THE Backend_API SHALL limit conversation history to the most recent 20 messages when calling DeepSeek_API

### Requirement 10: Backend Configuration

**User Story:** As a developer, I want to configure the DeepSeek API settings, so that the system can connect to the AI service.

#### Acceptance Criteria

1. THE Backend_API SHALL read the DeepSeek API key from an environment variable (DEEPSEEK_API_KEY) or configuration file (config.json)
2. WHEN receiving a chat request, THE Backend_API SHALL use the deepseek-chat model for conversations
3. IF the DEEPSEEK_API_KEY environment variable is not set and config.json is missing, THE Backend_API SHALL log an error and exit with a fatal error
4. IF the DeepSeek_API returns an authentication error, THE Backend_API SHALL return HTTP 401 with an error message

### Requirement 11: CORS Support

**User Story:** As a developer, I want the backend to support cross-origin requests, so that the frontend can communicate with the backend.

#### Acceptance Criteria

1. THE Backend_API SHALL include CORS headers in all HTTP responses, consisting of Access-Control-Allow-Origin header with the configured frontend origin value, Access-Control-Allow-Methods header with allowed methods POST and OPTIONS, and Access-Control-Allow-Headers header with allowed header Content-Type
2. THE Backend_API SHALL handle OPTIONS preflight requests by returning HTTP 200 with the same CORS headers as specified in criterion 1
3. THE Backend_API SHALL read the allowed frontend origin from an environment variable CORS_ORIGIN or configuration file, and SHALL use "http://localhost:3000" as the default value if neither is configured