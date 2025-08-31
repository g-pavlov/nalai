/**
 * API Communication Module
 * Handles all API requests and message sending
 */

import { buildApiUrl, API_CONFIG } from './config.js';
import { NetworkManager } from './network.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { getCurrentThreadId, setCurrentThreadId, getProcessingStatus, setProcessing, getFullMessageContent, setFullMessageContent } from './state.js';
import { getRequestHeaders, buildRequestPayload, getMessageConfig } from './settings.js';
import { Validator } from './validator.js';
import { setupMessageProcessing, cleanupMessageProcessing, handleMessageError } from './messages.js';
import { createAssistantMessageElement } from './messages.js';
import { DOM } from './dom.js';
import { parseSSEStream, routeEventToStateMachine } from './eventParser.js';


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
    // Always use the messages endpoint for sending messages
    const url = buildApiUrl(API_CONFIG.URL_TEMPLATES.MESSAGES);
    
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
        
        // Extract conversation ID from response body for non-streaming responses
        let conversationIdFromBody = null;
        if (!isStreamingEnabled) {
            try {
                const responseBody = await response.clone().json();
                conversationIdFromBody = responseBody.conversation_id;
            } catch (error) {
                Logger.warn('Failed to extract conversation ID from response body', { error });
            }
        }
        
        // Handle thread ID - pass conversation ID from body if available
        handleThreadIdResponse(response, conversationIdFromBody);

        // Process response based on type
        Logger.info('Processing API response', {
            isStreamingEnabled,
            responseType: isStreamingEnabled ? 'streaming' : 'non-streaming',
            hasStateMachine: !!assistantMessageDiv.stateMachine
        });
        
        if (isStreamingEnabled) {
            await handleStreamingResponseWithStateMachine(response, assistantMessageDiv);
        } else {
            await handleNonStreamingResponseWithStateMachine(response, assistantMessageDiv);
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

async function handleStreamingResponseWithStateMachine(response, assistantMessageDiv) {
    Logger.info('Starting streaming response with state machine');
    
    // Parse SSE stream and route events to state machine
    await parseSSEStream(
        response,
        routeEventToStateMachine,
        () => Logger.info('Streaming response completed'),
        (error) => {
            Logger.error('Error in streaming response', { error });
            throw error;
        }
    );
}

async function handleNonStreamingResponseWithStateMachine(response, assistantMessageDiv) {
    try {
        const responseData = await response.json();
        
        Logger.info('Processing non-streaming response with state machine', {
            hasStateMachine: !!assistantMessageDiv.stateMachine,
            responseData: JSON.stringify(responseData).substring(0, 200) + '...'
        });
        
        // For non-streaming responses, we can create a single content update
        if (assistantMessageDiv.stateMachine && responseData.content) {
            assistantMessageDiv.stateMachine.updateContentProgressive(responseData.content);
        } else {
            Logger.warn('No state machine or content found for non-streaming response');
        }
        
    } catch (error) {
        Logger.error('Error processing non-streaming response', { error });
        throw error;
    }
}

function handleThreadIdResponse(response, conversationIdFromBody = null) {
    // Try to get conversation ID from response header first (for backward compatibility)
    let conversationId = response.headers.get('X-Conversation-ID');
    
    // If not in header, use the one from response body
    if (!conversationId && conversationIdFromBody) {
        conversationId = conversationIdFromBody;
        Logger.info('Using conversation ID from response body', { 
            conversationId, 
            conversationIdType: typeof conversationId,
            hasConversationId: !!conversationId,
            currentThreadId: getCurrentThreadId(),
            willUpdate: conversationId && conversationId !== getCurrentThreadId()
        });
    } else if (conversationId) {
        Logger.info('Using conversation ID from response header', { 
            conversationId, 
            conversationIdType: typeof conversationId,
            hasConversationId: !!conversationId,
            currentThreadId: getCurrentThreadId(),
            willUpdate: conversationId && conversationId !== getCurrentThreadId()
        });
    }
    
    if (conversationId && conversationId !== getCurrentThreadId()) {
        // Validate that it's a proper domain-prefixed ID
        if (/^conv_[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{10,}$/i.test(conversationId)) {
            setCurrentThreadId(conversationId);
            Logger.info('New conversation thread started', { 
                conversationId,
                source: conversationIdFromBody ? 'response body' : 'response header'
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
            Logger.warn('Invalid conversation ID format received', { conversationId });
        }
    }
}
