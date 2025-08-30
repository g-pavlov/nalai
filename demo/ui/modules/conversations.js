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
        
        // Show conversation indicator only after successful load
        showConversationIndicator();
        
        Logger.info('Conversation loaded successfully', { conversationId });
        
    } catch (error) {
        Logger.error('Failed to load conversation', { conversationId, error });
        if (showUserErrors) {
            ErrorHandler.showUserError(`Failed to load conversation: ${error.message}`);
        }
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
                <div class="conversation-metadata-content">
                    <span class="conversation-metadata-icon">📋</span>
                    <div class="conversation-metadata-text">
                        <strong>Conversation Info:</strong> 
                        ${metadata.title || 'Untitled'} 
                        ${status ? `(${status})` : ''}
                        ${conversation.created_at ? ` - Created: ${new Date(conversation.created_at).toLocaleString()}` : ''}
                    </div>
                </div>
            `;
            DOM.chatContainer.appendChild(metadataDiv);
        }
        
        // Load messages with compression of AI responses and tool calls
        let i = 0;
        while (i < messages.length) {
            const message = messages[i];
            let messageType = message.role;
            
            // Map API message types to UI message types
            if (messageType === 'assistant') {
                messageType = 'assistant';
            } else if (messageType === 'user') {
                messageType = 'human';
            } else if (messageType === 'tool') {
                messageType = 'tool';
            }
            
            // Extract text content from content array
            const textContent = extractTextContent(message.content);
            
            if (messageType === 'assistant') {
                // Check if this AI message has tool calls and if there are tool messages following it
                const toolCalls = message.tool_calls || [];
                const followingToolMessages = [];
                
                // Look ahead to find tool messages that belong to this AI response
                let j = i + 1;
                while (j < messages.length && messages[j].role === 'tool') {
                    const toolMessage = messages[j];
                    const toolCallId = toolMessage.tool_call_id;
                    
                    // Check if this tool message corresponds to one of the tool calls in the AI message
                    const isRelatedToolCall = toolCalls.some(tc => tc.id === toolCallId);
                    
                    if (isRelatedToolCall) {
                        followingToolMessages.push(toolMessage);
                        j++;
                    } else {
                        break;
                    }
                }
                
                // If we have tool calls and related tool messages, compress them into a single response
                if (toolCalls.length > 0 && followingToolMessages.length > 0) {
                    // Look ahead for a final AI response that follows the tool messages
                    let finalAiResponse = '';
                    let finalIndex = j;
                    
                    // Check if there's an AI response immediately following the tool messages
                    if (j < messages.length && messages[j].role === 'assistant') {
                        const finalMessage = messages[j];
                        finalAiResponse = extractTextContent(finalMessage.content);
                        finalIndex = j + 1;
                    }
                    
                    // Create a compressed response with tool calls and their results
                    const compressedToolCalls = toolCalls.map(tc => {
                        const correspondingToolMessage = followingToolMessages.find(tm => tm.tool_call_id === tc.id);
                        return {
                            id: tc.id,
                            name: tc.name,
                            args: tc.args || {},
                            tool_call_id: tc.id,
                            content: correspondingToolMessage ? extractTextContent(correspondingToolMessage.content) : null,
                            status: correspondingToolMessage ? 'completed' : 'pending',
                            source: 'conversation_load'
                        };
                    });
                    
                    // Combine the initial AI response with the final AI response if present
                    const combinedContent = finalAiResponse ? `${textContent}\n\n${finalAiResponse}` : textContent;
                    
                    // Add the compressed AI response
                    await addMessage(combinedContent, messageType, {
                        name: message.name,
                        tool_call_id: message.tool_call_id,
                        toolCalls: compressedToolCalls
                    });
                    
                    // Skip the tool messages and final AI response we've already processed
                    i = finalIndex;
                } else {
                    // Regular AI message without tool calls or tool responses
                    await addMessage(textContent, messageType, {
                        name: message.name,
                        tool_call_id: message.tool_call_id,
                        toolCalls: toolCalls
                    });
                    i++;
                }
            } else {
                // Non-assistant messages (human, tool) - add normally
                await addMessage(textContent, messageType, {
                    name: message.name,
                    tool_call_id: message.tool_call_id,
                    toolCalls: message.tool_calls || []
                });
                i++;
            }
            
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

/**
 * Extract text content from message content array
 * @param {string|Array} content - Message content (string or array of content blocks)
 * @returns {string} - Extracted text content
 */
function extractTextContent(content) {
    if (typeof content === 'string') {
        return content;
    }
    
    if (Array.isArray(content)) {
        let textContent = '';
        for (const contentBlock of content) {
            if (contentBlock.type === 'text' && contentBlock.text) {
                textContent += contentBlock.text;
            }
        }
        return textContent;
    }
    
    // Fallback for unexpected content types
    return String(content);
}

function showConversationIndicator() {
    // Show a flash info message instead of persistent indicator
    ErrorHandler.showInfoMessage('Continuing previous conversation...', 3000);
}
