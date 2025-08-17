/**
 * Message Management Module
 * Handles message display and UI updates
 */

import { DOM } from './dom.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { setCurrentThreadId, setProcessing, getProcessingStatus } from './state.js';

export function createAssistantMessageElement() {
    const assistantMessageDiv = document.createElement('div');
    assistantMessageDiv.className = 'message assistant-message fade-in';
    assistantMessageDiv.textContent = '';
    DOM.chatContainer.appendChild(assistantMessageDiv);
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
    return assistantMessageDiv;
}

export function updateMessageContent(assistantMessageDiv, content) {
    if (!assistantMessageDiv) {
        Logger.warn('No assistant message element found for content update');
        return;
    }
    
    const messageContent = assistantMessageDiv.querySelector('.message-content');
    if (messageContent) {
        messageContent.innerHTML = marked.parse(content);
    }
}

export function showWelcomeMessage() {
    const welcomeMessage = `
# Welcome to nalAI Chat Interface! 🤖

This is an AI assistant that can help you with various tasks. You can:

- **Ask questions** and get intelligent responses
- **Use tools** to perform actions (when available)
- **Review and approve** tool calls before execution
- **Manage conversations** and view chat history

## Getting Started

Simply type your message below and press Enter or click the Send button to start chatting!

## Features

- **Streaming responses** for real-time interaction
- **Conversation management** to save and load chats
- **Tool integration** for enhanced capabilities
- **Human review** for safety and control

Start by asking me something!
    `;
    
    addMessage('assistant', welcomeMessage);
}

export function showConversationIndicator() {
    // Show a flash info message instead of persistent indicator
    ErrorHandler.showInfoMessage('Continuing previous conversation...', 3000);
}

export function addMessage(content, type, options = {}) {
    try {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message fade-in`;
        
        if (type === 'assistant') {
            updateMessageContent(messageDiv, content);
        } else if (type === 'tool') {
            // Handle tool messages with additional metadata
            const toolName = options.name || 'Unknown tool';
            const toolCallId = options.tool_call_id || '';
            messageDiv.innerHTML = `
                <div class="tool-message">
                    <div class="tool-header">
                        <span class="tool-icon">🔧</span>
                        <span class="tool-name">${toolName}</span>
                        ${toolCallId ? `<span class="tool-call-id">${toolCallId}</span>` : ''}
                    </div>
                    <div class="tool-content">${content}</div>
                </div>
            `;
        } else {
            messageDiv.textContent = content;
        }
        
        DOM.chatContainer.appendChild(messageDiv);
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
        
    } catch (error) {
        ErrorHandler.handleError(error, 'Adding message');
    }
}

export function startNewConversation() {
    try {
        setCurrentThreadId(null);
        
        DOM.chatContainer.innerHTML = '';
        showWelcomeMessage();
        
        // Hide conversation indicator
        const indicator = document.querySelector('.conversation-indicator');
        if (indicator) {
            indicator.remove();
        }
        
        Logger.info('Started new conversation');
        ErrorHandler.showSuccessMessage('New conversation started');
        
    } catch (error) {
        ErrorHandler.handleError(error, 'Starting new conversation');
    }
}

export function setupMessageProcessing(message) {
    addMessage(message, 'human');
    DOM.messageInput.value = '';
    setProcessing(true);
    DOM.sendButton.disabled = true;
    DOM.loading.style.display = 'block';
    
    // We'll need to get config from settings module
    const config = { isStreamingEnabled: DOM.streamingToggle.checked };
    DOM.loadingText.textContent = config.isStreamingEnabled ? 
        '🤔 Thinking...' : 
        '⏳ Processing...';
}

export function cleanupMessageProcessing() {
    setProcessingStatus(false);
    DOM.sendButton.disabled = false;
    DOM.messageInput.disabled = false;
    DOM.messageInput.focus();
}

export function handleMessageError(error) {
    Logger.error('Message processing failed', { error: error?.message || 'Unknown error' });
    
    // Create error message element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message error-message fade-in';
    errorDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">❌</span>
            <div>
                <strong>Failed to send message:</strong> ${error?.message || 'Unknown error'}
                <br>
                <small style="opacity: 0.7;">Please try again or check your connection.</small>
            </div>
        </div>
    `;
    
    DOM.chatContainer.appendChild(errorDiv);
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
}

// This function will be moved to the events module, but we need it here for now
function handleInputChange() {
    const hasContent = DOM.messageInput.value.trim().length > 0;
    DOM.sendButton.disabled = !hasContent || getProcessingStatus();
}
