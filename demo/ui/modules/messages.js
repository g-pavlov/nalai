/**
 * Message Management Module
 * Handles message display and UI updates
 */

import { DOM } from './dom.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { setCurrentThreadId, setProcessing, getProcessingStatus } from './state.js';
import { addToolCallsIndicatorToMessage } from './toolCalls.js';
import { resetStreamingProgressState } from './streaming.js';

export function createAssistantMessageElement() {
    // Reset streaming state to ensure clean state for new message
    resetStreamingProgressState();
    
    // Clear any expanded tools panels from previous messages (but keep the indicators)
    const existingToolsPanels = DOM.chatContainer.querySelectorAll('.tools-panel');
    existingToolsPanels.forEach(panel => {
        if (panel.classList.contains('expanded')) {
            panel.classList.remove('expanded');
            // Remove the panel after a short delay to allow for smooth transition
            setTimeout(() => {
                if (panel.parentNode) {
                    panel.remove();
                }
            }, 150);
        }
    });
    
    const assistantMessageDiv = document.createElement('div');
    assistantMessageDiv.className = 'message assistant-message fade-in';
    assistantMessageDiv.textContent = '';
    DOM.chatContainer.appendChild(assistantMessageDiv);
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
    
    Logger.info('Created new assistant message element, reset streaming state, and cleared expanded tools panels');
    return assistantMessageDiv;
}

export function updateMessageContent(element, content) {
    // If no element is provided (for resume streams), find the last assistant message
    if (!element) {
        element = DOM.chatContainer.querySelector('.assistant-message:last-child');
        if (!element) {
            Logger.warn('No assistant message element found for content update');
            return;
        }
        Logger.info('Found last assistant message element for resume stream update');
    }
    
    Logger.info('Updating message content', { 
        contentLength: content?.length || 0,
        hasElement: !!element,
        elementClass: element?.className 
    });
    
    try {
        element.innerHTML = marked.parse(content);
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
    } catch (error) {
        ErrorHandler.handleParsingError(error, content, 'Markdown parsing');
        element.textContent = content; // Fallback to plain text
    }
}

export function showWelcomeMessage() {
    const welcomeMessage = 'Hello! I\'m nalAI. I can help you with API integration, data processing, and more. What would you like to work on?';
    Logger.info('Showing welcome message');
    addMessage(welcomeMessage, 'assistant');
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
            
            // Add tool calls indicator if tool calls are provided
            if (options.toolCalls && options.toolCalls.length > 0) {
                addToolCallsIndicatorToMessage(
                    messageDiv, 
                    options.toolCalls.length, 
                    options.toolCalls
                );
            }
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
        
    } catch (error) {
        ErrorHandler.handleError(error, 'Starting new conversation');
    }
}

export function setupMessageProcessing(message) {
    addMessage(message, 'human');
    DOM.messageInput.value = '';
    setProcessing(true);
    DOM.sendButton.disabled = true;
    
    // Disable input field and change placeholder to indicate processing
    DOM.messageInput.disabled = true;
    DOM.messageInput.placeholder = 'Processing your request...';
}

export function cleanupMessageProcessing() {
    setProcessing(false);
    DOM.sendButton.disabled = false;
    
    // Re-enable input field and restore original placeholder
    DOM.messageInput.disabled = false;
    DOM.messageInput.placeholder = 'Type your message here...';
    
    // Trigger input change event to re-enable send button if there's content
    DOM.messageInput.dispatchEvent(new Event('input'));
}

export function handleMessageError(error) {
    Logger.error('Message processing failed', { error: error?.message || 'Unknown error' });
    
    // Create error message element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message error-message fade-in';
    errorDiv.innerHTML = `
        <div class="message-content-layout">
            <span class="message-icon">❌</span>
            <div>
                <strong>Failed to send message:</strong> ${error?.message || 'Unknown error'}
                <br>
                <small class="message-text-muted">Please try again or check your connection.</small>
            </div>
        </div>
    `;
    
    DOM.chatContainer.appendChild(errorDiv);
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
}
