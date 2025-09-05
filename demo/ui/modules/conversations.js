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
import { ResponseStateMachine } from './responses.js';
import { addToolCallsIndicatorToMessage } from './toolCalls.js';

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
                        let status = 'pending';
                        let content = null;
                        
                        if (correspondingToolMessage) {
                            content = extractTextContent(correspondingToolMessage.content);
                            // Determine status based on content
                            if (content.toLowerCase().includes('user rejected') || content.toLowerCase().includes('rejected')) {
                                status = 'rejected';
                            } else {
                                status = 'completed';
                            }
                        }
                        
                        return {
                            id: tc.id,
                            name: tc.name,
                            args: tc.args || {},
                            tool_call_id: tc.id,
                            content: content,
                            status: status,
                            source: 'conversation_load'
                        };
                    });
                    
                    // Combine the initial AI response with the final AI response if present
                    const combinedContent = finalAiResponse ? `${textContent}\n\n${finalAiResponse}` : textContent;
                    
                    // Create proper assistant message with ResponseStateMachine for markdown rendering
                    await createLoadedAssistantMessage(combinedContent, {
                        name: message.name,
                        tool_call_id: message.tool_call_id,
                        toolCalls: compressedToolCalls
                    });
                    
                    // Skip the tool messages and final AI response we've already processed
                    i = finalIndex;
                } else {
                    // Regular AI message without tool calls or tool responses
                    await createLoadedAssistantMessage(textContent, {
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
 * Create an assistant message element for loaded conversations with proper markdown rendering
 * @param {string} content - The message content to render
 * @param {Object} options - Additional options for the message
 */
async function createLoadedAssistantMessage(content, options = {}) {
    try {
        // Create the message container
        const messageDiv = document.createElement('div');
        messageDiv.className = 'message assistant-message fade-in';
        
        // Add unique message ID for state machine tracking
        messageDiv.dataset.messageId = `msg_loaded_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
        
        // Initialize response state machine for this message
        const stateMachine = new ResponseStateMachine(messageDiv);
        messageDiv.stateMachine = stateMachine;
        
        // Add tool calls indicator if tool calls are provided
        if (options.toolCalls && options.toolCalls.length > 0) {
            addToolCallsIndicatorToMessage(
                messageDiv, 
                options.toolCalls.length, 
                options.toolCalls
            );
        }
        
        // Add the message to the container
        DOM.chatContainer.appendChild(messageDiv);
        
        // Render the content with markdown
        if (content && content.trim()) {
            // Use the state machine to render the content with markdown
            stateMachine.updateContentProgressive(content.trim());
        }
        
        // Scroll to show the new message
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
        
        Logger.info('Created loaded assistant message with markdown rendering', {
            messageId: messageDiv.dataset.messageId,
            contentLength: content.length
        });
        
    } catch (error) {
        Logger.error('Failed to create loaded assistant message', { error, content });
        // Fallback to simple text if markdown rendering fails
        await addMessage(content, 'assistant', options);
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
            if (typeof contentBlock === 'string') {
                textContent += contentBlock;
            } else if (contentBlock.type === 'text' && contentBlock.text) {
                textContent += contentBlock.text;
            } else if (contentBlock.type === 'image') {
                // Add placeholder text for images
                const source = contentBlock.source_type === 'url' ? contentBlock.url : 'base64 image';
                textContent += `[Image: ${source}]`;
            } else if (contentBlock.type === 'audio') {
                // Add placeholder text for audio
                const source = contentBlock.source_type === 'url' ? contentBlock.url : 'base64 audio';
                textContent += `[Audio: ${source}]`;
            } else if (contentBlock.type === 'file') {
                // Add placeholder text for files
                const source = contentBlock.source_type === 'url' ? contentBlock.url : 'base64 file';
                textContent += `[File: ${source}]`;
            }
        }
        return textContent;
    }
    
    // Fallback for unexpected content types
    return String(content);
}

/**
 * Render rich content blocks as HTML elements
 * @param {string|Array} content - Message content (string or array of content blocks)
 * @returns {string} - HTML string with rich content
 */
function renderRichContent(content) {
    if (typeof content === 'string') {
        return escapeHtml(content);
    }
    
    if (!Array.isArray(content)) {
        return escapeHtml(String(content));
    }
    
    let htmlContent = '';
    for (const contentBlock of content) {
        if (typeof contentBlock === 'string') {
            htmlContent += escapeHtml(contentBlock);
        } else if (contentBlock.type === 'text' && contentBlock.text) {
            htmlContent += escapeHtml(contentBlock.text);
        } else if (contentBlock.type === 'image') {
            htmlContent += renderImageBlock(contentBlock);
        } else if (contentBlock.type === 'audio') {
            htmlContent += renderAudioBlock(contentBlock);
        } else if (contentBlock.type === 'file') {
            htmlContent += renderFileBlock(contentBlock);
        }
    }
    return htmlContent;
}

/**
 * Render image content block as HTML
 * @param {Object} imageBlock - Image content block
 * @returns {string} - HTML string for image
 */
function renderImageBlock(imageBlock) {
    if (imageBlock.source_type === 'url' && imageBlock.url) {
        return `<div class="content-block image-block">
            <img src="${escapeHtml(imageBlock.url)}" alt="Image" style="max-width: 100%; height: auto; border-radius: 8px; margin: 8px 0;">
            <div class="image-caption">Image from URL</div>
        </div>`;
    } else if (imageBlock.source_type === 'base64' && imageBlock.data) {
        const mimeType = imageBlock.mime_type || 'image/jpeg';
        return `<div class="content-block image-block">
            <img src="data:${mimeType};base64,${imageBlock.data}" alt="Image" style="max-width: 100%; height: auto; border-radius: 8px; margin: 8px 0;">
            <div class="image-caption">Base64 Image</div>
        </div>`;
    }
    return '<div class="content-block image-block error">[Invalid image block]</div>';
}

/**
 * Render audio content block as HTML
 * @param {Object} audioBlock - Audio content block
 * @returns {string} - HTML string for audio
 */
function renderAudioBlock(audioBlock) {
    if (audioBlock.source_type === 'url' && audioBlock.url) {
        return `<div class="content-block audio-block">
            <audio controls style="width: 100%; margin: 8px 0;">
                <source src="${escapeHtml(audioBlock.url)}" type="${audioBlock.mime_type || 'audio/mpeg'}">
                Your browser does not support the audio element.
            </audio>
            <div class="audio-caption">Audio from URL</div>
        </div>`;
    } else if (audioBlock.source_type === 'base64' && audioBlock.data) {
        const mimeType = audioBlock.mime_type || 'audio/mpeg';
        return `<div class="content-block audio-block">
            <audio controls style="width: 100%; margin: 8px 0;">
                <source src="data:${mimeType};base64,${audioBlock.data}" type="${mimeType}">
                Your browser does not support the audio element.
            </audio>
            <div class="audio-caption">Base64 Audio</div>
        </div>`;
    }
    return '<div class="content-block audio-block error">[Invalid audio block]</div>';
}

/**
 * Render file content block as HTML
 * @param {Object} fileBlock - File content block
 * @returns {string} - HTML string for file
 */
function renderFileBlock(fileBlock) {
    const fileName = fileBlock.name || 'Unknown file';
    const fileSize = fileBlock.size ? ` (${formatFileSize(fileBlock.size)})` : '';
    
    if (fileBlock.source_type === 'url' && fileBlock.url) {
        return `<div class="content-block file-block">
            <a href="${escapeHtml(fileBlock.url)}" target="_blank" rel="noopener noreferrer" 
               style="display: inline-flex; align-items: center; padding: 8px 12px; background: #f0f0f0; border-radius: 6px; text-decoration: none; color: #333; margin: 4px 0;">
                <span style="margin-right: 8px;">📄</span>
                <span>${escapeHtml(fileName)}${fileSize}</span>
            </a>
            <div class="file-caption">File from URL</div>
        </div>`;
    } else if (fileBlock.source_type === 'base64' && fileBlock.data) {
        // For base64 files, we can't directly link to them, so show info
        return `<div class="content-block file-block">
            <div style="display: inline-flex; align-items: center; padding: 8px 12px; background: #f0f0f0; border-radius: 6px; margin: 4px 0;">
                <span style="margin-right: 8px;">📄</span>
                <span>${escapeHtml(fileName)}${fileSize}</span>
            </div>
            <div class="file-caption">Base64 File (${formatFileSize(fileBlock.data.length)})</div>
        </div>`;
    }
    return '<div class="content-block file-block error">[Invalid file block]</div>';
}

/**
 * Format file size in human readable format
 * @param {number} bytes - File size in bytes
 * @returns {string} - Formatted file size
 */
function formatFileSize(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
}

/**
 * Escape HTML special characters
 * @param {string} text - Text to escape
 * @returns {string} - Escaped text
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

function showConversationIndicator() {
    // Show a flash info message instead of persistent indicator
    ErrorHandler.showInfoMessage('Continuing previous conversation...', 3000);
}

// Export functions for use in other modules
export { renderRichContent, escapeHtml, extractTextContent };
