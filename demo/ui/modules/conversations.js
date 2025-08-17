/**
 * Conversations Module
 * Handles conversation loading and management
 */

import { DOM } from './dom.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { NetworkManager } from './network.js';
import { buildApiUrl, API_CONFIG } from './config.js';
import { getRequestHeaders } from './settings.js';
import { setCurrentThreadId } from './state.js';
import { addMessage } from './messages.js';

export async function loadConversation(conversationId, showUserErrors = true) {
    try {
        Logger.info('Loading conversation', { conversationId });
        
        // Show loading state
        DOM.loading.style.display = 'block';
        DOM.loadingText.textContent = '📂 Loading conversation...';
        
        // Build the API URL
        const url = buildApiUrl(API_CONFIG.URL_TEMPLATES.CONVERSATION, { conversation_id: conversationId });
        const headers = getRequestHeaders(false, false); // No streaming for loading
        
        // Make the API request
        const response = await NetworkManager.fetchWithRetry(url, {
            method: 'GET',
            headers
        });
        
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorBody = await response.text();
                if (errorBody) {
                    const errorJson = JSON.parse(errorBody);
                    if (errorJson.detail) {
                        errorMessage += ` - ${errorJson.detail}`;
                    }
                }
            } catch (parseError) {
                Logger.warn('Could not parse error response', { parseError });
            }
            
            // Create error with status code for proper handling
            const error = new Error(errorMessage);
            error.status = response.status;
            throw error;
        }
        
        const conversation = await response.json();
        
        // Clear current conversation
        DOM.chatContainer.innerHTML = '';
        
        // Load conversation messages
        await loadConversationMessages(conversation);
        
        // Update current thread ID
        setCurrentThreadId(conversation.conversation_id);
        
        // Save as last conversation for future loads
        localStorage.setItem('nalai_last_conversation_id', conversation.conversation_id);
        
        // Show conversation indicator only after successful load
        showConversationIndicator();
        
        Logger.info('Conversation loaded successfully', { conversationId });
        if (showUserErrors) {
            ErrorHandler.showSuccessMessage('Conversation loaded successfully');
        }
        
    } catch (error) {
        Logger.error('Failed to load conversation', { conversationId, error });
        if (showUserErrors) {
            ErrorHandler.showUserError(`Failed to load conversation: ${error.message}`);
        }
    } finally {
        DOM.loading.style.display = 'none';
    }
}

async function loadConversationMessages(conversation) {
    try {
        const { messages, metadata, status } = conversation;
        
        // Add conversation metadata if available
        if (metadata && Object.keys(metadata).length > 0) {
            const metadataDiv = document.createElement('div');
            metadataDiv.className = 'conversation-metadata fade-in';
            metadataDiv.innerHTML = `
                <div style="display: flex; align-items: center; gap: 8px; padding: 8px 12px; background: rgba(0,0,0,0.05); border-radius: 8px; margin-bottom: 16px;">
                    <span style="font-size: 14px;">📋</span>
                    <div style="font-size: 12px; color: #666;">
                        <strong>Conversation Info:</strong> 
                        ${metadata.title || 'Untitled'} 
                        ${status ? `(${status})` : ''}
                        ${conversation.created_at ? ` - Created: ${new Date(conversation.created_at).toLocaleString()}` : ''}
                    </div>
                </div>
            `;
            DOM.chatContainer.appendChild(metadataDiv);
        }
        
        // Load messages
        for (const message of messages) {
            let messageType = message.type;
            
            // Map API message types to UI message types
            if (messageType === 'ai') {
                messageType = 'assistant';
            } else if (messageType === 'human') {
                messageType = 'human';
            } else if (messageType === 'tool') {
                messageType = 'tool';
            }
            
            await addMessage(message.content, messageType, {
                name: message.name,
                tool_call_id: message.tool_call_id
            });
            
            // Small delay to prevent UI blocking
            await new Promise(resolve => setTimeout(resolve, 10));
        }
        
        // Scroll to bottom
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
        
    } catch (error) {
        Logger.error('Failed to load conversation messages', { error });
        throw error;
    }
}

function showConversationIndicator() {
    // Show a flash info message instead of persistent indicator
    ErrorHandler.showInfoMessage('Continuing previous conversation...', 3000);
}
