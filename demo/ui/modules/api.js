/**
 * API Communication Module
 * Handles all API requests and message sending
 */

import { buildApiUrl, API_CONFIG } from './config.js';
import { NetworkManager } from './network.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { getCurrentThreadId, setCurrentThreadId } from './state.js';
import { getRequestHeaders, buildRequestPayload, getMessageConfig } from './settings.js';
import { normalizeThreadId } from './validator.js';
import { Validator } from './validator.js';
import { setupMessageProcessing, cleanupMessageProcessing, handleMessageError } from './messages.js';
import { createAssistantMessageElement } from './messages.js';
import { setFullMessageContent, getFullMessageContent } from './state.js';
import { DOM } from './dom.js';

export async function sendMessage() {
    if (getProcessingStatus()) {
        Logger.warn('Message already being processed', { isProcessing: getProcessingStatus() });
        return;
    }

    const message = DOM.messageInput.value.trim();
    
    try {
        // Validate input
        const validatedMessage = Validator.validateMessage(message);
        
        // Check network status
        if (!NetworkManager.isOnline()) {
            ErrorHandler.showUserError('No internet connection. Please check your network and try again.');
            return;
        }

        // Setup UI state
        setupMessageProcessing(validatedMessage);
        
        // Get configuration
        const config = getMessageConfig();
        
        // Create assistant message element
        const assistantMessageDiv = createAssistantMessageElement();
        setFullMessageContent('');

        // Send request
        const response = await sendApiRequest(validatedMessage, config);
        
        // Process response
        await processApiResponse(response, assistantMessageDiv, config.isStreamingEnabled);

    } catch (error) {
        handleMessageError(error);
    } finally {
        cleanupMessageProcessing();
    }
}

async function sendApiRequest(message, config) {
    let url;
    let options;
    
    if (config.isStreamingEnabled) {
        url = buildApiUrl(API_CONFIG.URL_TEMPLATES.STREAM, {});
        options = {
            method: 'POST',
            headers: getRequestHeaders(true, true),
            body: JSON.stringify({
                input: [{
                    content: message,
                    type: 'human'
                }],
                model: config.model
            })
        };
    } else {
        url = buildApiUrl(API_CONFIG.URL_TEMPLATES.INVOKE, {});
        options = {
            method: 'POST',
            headers: getRequestHeaders(false, false),
            body: JSON.stringify({
                input: [{
                    content: message,
                    type: 'human'
                }],
                model: config.model
            })
        };
    }

    return await NetworkManager.fetchWithRetry(url, options);
}

async function processApiResponse(response, assistantMessageDiv, isStreamingEnabled) {
    if (isStreamingEnabled) {
        await handleStreamingResponse(response, assistantMessageDiv);
    } else {
        await handleNonStreamingResponse(response, assistantMessageDiv);
    }
}

async function handleNonStreamingResponse(response, assistantMessageDiv) {
    try {
        const data = await response.json();
        
        // Extract conversation ID if present
        if (data.conversation_id) {
            setCurrentThreadId(data.conversation_id);
        }
        
        // Process messages
        if (data.messages && Array.isArray(data.messages)) {
            for (const message of data.messages) {
                if (message.type === 'ai' && message.content) {
                    updateMessageContent(assistantMessageDiv, message.content);
                }
            }
        }
        
        // Auto-refresh conversations list after new conversation creation
        if (data.conversation_id && !getCurrentThreadId()) {
            try {
                await refreshConversationsList();
            } catch (error) {
                Logger.warn('Failed to auto-refresh conversations list', { error });
            }
        }
        
    } catch (error) {
        Logger.error('Failed to process non-streaming response', { error });
        throw error;
    }
}

function handleMessageError(error) {
    Logger.error('Message processing failed', { error: error?.message || 'Unknown error' });
    ErrorHandler.handleError(error, 'Message processing');
    cleanupMessageProcessing();
}

function setupMessageProcessing(message) {
    setProcessingStatus(true);
    DOM.sendButton.disabled = true;
    DOM.messageInput.disabled = true;
}

function cleanupMessageProcessing() {
    setProcessingStatus(false);
    DOM.sendButton.disabled = false;
    DOM.messageInput.disabled = false;
    DOM.messageInput.focus();
}

function createAssistantMessageElement() {
    const assistantMessageDiv = document.createElement('div');
    assistantMessageDiv.className = 'message assistant-message fade-in';
    assistantMessageDiv.innerHTML = '<div class="message-content">🤔 Thinking...</div>';
    DOM.messagesContainer.appendChild(assistantMessageDiv);
    return assistantMessageDiv;
}

function getMessageConfig() {
    return {
        isStreamingEnabled: getStreamingEnabled(),
        isNoCacheEnabled: getNoCacheEnabled(),
        model: getModelConfig()
    };
}
