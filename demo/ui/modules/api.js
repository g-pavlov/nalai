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
    
    if (getCurrentThreadId()) {
        // Continue existing conversation
        url = buildApiUrl(API_CONFIG.URL_TEMPLATES.CONVERSATION, { conversation_id: getCurrentThreadId() });
    } else {
        // Create new conversation
        url = buildApiUrl(API_CONFIG.URL_TEMPLATES.CONVERSATIONS);
    }
    
    const requestPayload = buildRequestPayload(message, config);
    const headers = getRequestHeaders(config.isStreamingEnabled, config.isNoCacheEnabled);
    
    Logger.info('Sending API request', { 
        url,
        isStreaming: config.isStreamingEnabled,
        hasThreadId: !!getCurrentThreadId(),
        payload: requestPayload
    });

    try {
        const response = await NetworkManager.fetchWithRetry(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(requestPayload)
        });
        
        // If response is not ok, capture the error body for detailed error messages
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            
            // Try to get the error details from the response body
            try {
                const errorBody = await response.text();
                if (errorBody) {
                    try {
                        const errorJson = JSON.parse(errorBody);
                        if (errorJson.detail) {
                            errorMessage += ` - ${errorJson.detail}`;
                        } else if (errorJson.message) {
                            errorMessage += ` - ${errorJson.message}`;
                        } else {
                            errorMessage += ` - ${errorBody}`;
                        }
                    } catch (parseError) {
                        errorMessage += ` - ${errorBody}`;
                    }
                }
            } catch (bodyError) {
                Logger.warn('Could not read error response body', { bodyError });
            }
            
            const error = new Error(errorMessage);
            error.response = response; // Attach response for error handling
            throw error;
        }
        
        return response;
    } catch (error) {
        if (error.message.includes('timed out')) {
            throw ErrorHandler.handleTimeoutError('API request');
        } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
            throw ErrorHandler.handleNetworkError(error, 'API request');
        } else {
            throw error;
        }
    }
}

async function processApiResponse(response, assistantMessageDiv, isStreamingEnabled) {
    try {
        Validator.validateApiResponse(response);
        
        // Handle thread ID
        handleThreadIdResponse(response);

        // Process response based on type
        if (isStreamingEnabled) {
            await handleStreamingResponse(response, assistantMessageDiv);
        } else {
            await handleNonStreamingResponse(response, assistantMessageDiv);
        }

    } catch (error) {
        if (error.message.includes('HTTP')) {
            const status = parseInt(error.message.match(/HTTP (\d+)/)?.[1] || '500');
            // Extract the full error message after the status code
            const fullErrorMatch = error.message.match(/HTTP \d+: (.+)/);
            const statusText = fullErrorMatch ? fullErrorMatch[1] : 'Unknown error';
            throw ErrorHandler.handleApiError(status, statusText, 'API response processing');
        } else {
            throw error;
        }
    }
}

function handleThreadIdResponse(response) {
    const conversationId = response.headers.get('X-Conversation-ID');
    Logger.info('Received conversation ID from response', { 
        conversationId, 
        conversationIdType: typeof conversationId,
        hasConversationId: !!conversationId,
        currentThreadId: getCurrentThreadId(),
        willUpdate: conversationId && conversationId !== getCurrentThreadId()
    });
    
            if (conversationId && conversationId !== getCurrentThreadId()) {
            const normalizedThreadId = normalizeThreadId(conversationId);
            if (normalizedThreadId) {
                setCurrentThreadId(normalizedThreadId);
                Logger.info('New conversation thread started', { 
                    originalConversationId: conversationId, 
                    normalizedThreadId 
                });
                
                // Auto-refresh conversations list when a new conversation is created
                // Import the refresh function dynamically to avoid circular imports
                import('./conversationsManager.js').then(module => {
                    if (module.refreshConversationsList) {
                        Logger.info('Auto-refreshing conversations list after new conversation creation');
                        module.refreshConversationsList();
                    }
                }).catch(error => {
                    Logger.warn('Failed to auto-refresh conversations list', { error });
                });
            } else {
                Logger.warn('Failed to normalize conversation ID', { conversationId });
            }
        }
}

// Import streaming functions
import { handleStreamingResponse, handleNonStreamingResponse } from './streaming.js';

// Import the processing status function
import { getProcessingStatus } from './state.js';
