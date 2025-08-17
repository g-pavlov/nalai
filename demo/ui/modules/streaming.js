/**
 * Streaming Module
 * Handles streaming and non-streaming response processing
 */

import { EVENT_TYPES, MESSAGE_TYPES } from './config.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { updateMessageContent, cleanupMessageProcessing } from './messages.js';
import { setFullMessageContent, getFullMessageContent } from './state.js';
import { Validator } from './validator.js';
import { createInterruptUI } from './interrupts.js';

export async function handleStreamingResponse(response, assistantMessageDiv) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let hasReceivedEvents = false;
    let buffer = '';
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                        Logger.info('Stream completed with [DONE] event');
                        break;
                    }
                    
                    if (!data || data.trim() === '') continue;
                    
                    try {
                        const event = JSON.parse(data);
                        hasReceivedEvents = true;
                        
                        Validator.validateEventData(event);
                        processStreamEvent(event, assistantMessageDiv);
                        
                    } catch (error) {
                        ErrorHandler.handleParsingError(error, data, 'Stream event parsing');
                    }
                }
            }
        }
        
        handleStreamingCompletion(hasReceivedEvents, assistantMessageDiv);
        
    } catch (error) {
        ErrorHandler.handleError(error, 'Streaming response processing');
    } finally {
        reader.releaseLock();
    }
}

export function processStreamEvent(event, assistantMessageDiv) {
    if (Array.isArray(event) && event.length === 2) {
        const [eventType, eventData] = event;
        
        switch (eventType) {
            case EVENT_TYPES.MESSAGES:
                if (Array.isArray(eventData)) {
                    handleMessageEvent(eventData, assistantMessageDiv);
                }
                break;
            case EVENT_TYPES.UPDATES:
                if (typeof eventData === 'object') {
                    handleUpdateEvent(eventData, assistantMessageDiv);
                }
                break;
            case EVENT_TYPES.ERROR:
                handleErrorEvent(eventData, assistantMessageDiv);
                break;
            default:
                Logger.warn('Unknown event type', { eventType, eventData });
        }
    } else if (event.error) {
        // Handle error events that come as objects with error property
        handleErrorEvent(event.error, assistantMessageDiv);
    } else {
        Logger.warn('Unexpected event format', { event });
    }
}

function handleMessageEvent(eventData, assistantMessageDiv) {
    // Pre-process to check if this is an internal node message
    const isInternalNode = eventData.some(message => 
        message.langgraph_node && message.langgraph_node !== 'call_model'
    );
    
    if (isInternalNode) {
        const nodeName = eventData.find(m => m.langgraph_node)?.langgraph_node;
        Logger.info('Skipped internal node message batch', { 
            node: nodeName, 
            messageCount: eventData.length 
        });
        return; // Skip the entire batch
    }
    
    for (const message of eventData) {
        if (message.type === MESSAGE_TYPES.AI_CHUNK && message.content) {
            const currentContent = getFullMessageContent();
            const newContent = currentContent + message.content;
            setFullMessageContent(newContent);
            updateMessageContent(assistantMessageDiv, newContent);
        } else if (message.type === MESSAGE_TYPES.AI && message.content) {
            setFullMessageContent(message.content);
            updateMessageContent(assistantMessageDiv, message.content);
        } else if (message.type === MESSAGE_TYPES.TOOL && message.content) {
            createToolCallElement(assistantMessageDiv, `🔧 Tool Response: ${message.name || 'Unknown tool'}`);
        }
    }
}

function handleUpdateEvent(eventData, assistantMessageDiv) {
    for (const [updateKey, updateValue] of Object.entries(eventData)) {
        switch (updateKey) {
            case EVENT_TYPES.INTERRUPT:
                handleInterruptEvent(updateValue, assistantMessageDiv);
                break;
            case EVENT_TYPES.CALL_MODEL:
                handleCallModelEvent(updateValue, assistantMessageDiv);
                break;
            case EVENT_TYPES.CALL_API:
                handleCallApiEvent(updateValue, assistantMessageDiv);
                break;
            case EVENT_TYPES.CHECK_CACHE:
            case EVENT_TYPES.LOAD_API_SUMMARIES:
            case EVENT_TYPES.LOAD_API_SPECS:
            case EVENT_TYPES.SELECT_RELEVANT_APIS:
            case EVENT_TYPES.HUMAN_REVIEW:
                // These are backend processing events, no UI updates needed
                break;
            default:
                Logger.warn('Unknown update key', { updateKey, updateValue });
        }
    }
}

function handleErrorEvent(errorData, assistantMessageDiv) {
    Logger.error('Error event received from server', { errorData });
    
    let errorMessage = 'An error occurred while processing your request.';
    
    // Try to extract meaningful error message from different error formats
    if (typeof errorData === 'string') {
        errorMessage = errorData;
    } else if (errorData && typeof errorData === 'object') {
        if (errorData.message) {
            errorMessage = errorData.message;
        } else if (errorData.error && errorData.error.message) {
            errorMessage = errorData.error.message;
        } else if (errorData.detail) {
            errorMessage = errorData.detail;
        }
    }
    
    // Create error message element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message error-message fade-in';
    errorDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">❌</span>
            <div>
                <strong>Server Error:</strong> ${errorMessage}
                <br>
                <small style="opacity: 0.7;">Please try again or check your input.</small>
            </div>
        </div>
    `;
    
    // Insert error message after the assistant message
    if (assistantMessageDiv && assistantMessageDiv.parentNode) {
        assistantMessageDiv.parentNode.insertBefore(errorDiv, assistantMessageDiv.nextSibling);
    } else {
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.appendChild(errorDiv);
        }
    }
    
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
    
    // Clear processing state
    cleanupMessageProcessing();
}

function handleInterruptEvent(updateValue, assistantMessageDiv) {
    Logger.info('Interrupt detected', { updateValue });
    
    const interruptInfo = parseInterruptString(updateValue[0]);
    const actionRequest = interruptInfo?.action_request || {};
    
    createInterruptUI(assistantMessageDiv, actionRequest, interruptInfo);
    
    window.currentInterrupt = {
        value: interruptInfo,
        resumable: true
    };
}

function parseInterruptString(interruptString) {
    try {
        const valueMatch = interruptString.match(/value=\[([^\]]+)\]/);
        if (!valueMatch) return null;

        let valueStr = valueMatch[1];
        valueStr = valueStr
            .replace(/'/g, '"')
            .replace(/True/g, 'true')
            .replace(/False/g, 'false')
            .replace(/None/g, 'null');

        return JSON.parse(valueStr);
    } catch (error) {
        Logger.warn('Failed to parse interrupt string, using fallback', { error: error.message });
        return parseInterruptFallback(interruptString);
    }
}

function parseInterruptFallback(interruptString) {
    try {
        const actionMatch = interruptString.match(/'action': '([^']+)'/);
        const argsMatch = interruptString.match(/'args': \{([^}]+)\}/);
        
        return {
            action_request: {
                action: actionMatch ? actionMatch[1] : 'Unknown tool',
                args: argsMatch ? JSON.parse('{' + argsMatch[1].replace(/'/g, '"').replace(/True/g, 'true').replace(/False/g, 'false') + '}') : {}
            }
        };
    } catch (error) {
        Logger.error('Fallback interrupt parsing failed', { error: error.message });
        return {
            action_request: {
                action: 'Unknown tool',
                args: {}
            }
        };
    }
}

function handleCallModelEvent(updateValue, assistantMessageDiv) {
    if (updateValue.messages) {
        for (const message of updateValue.messages) {
            if (message.type === MESSAGE_TYPES.AI && message.content) {
                setFullMessageContent(message.content);
                updateMessageContent(assistantMessageDiv, message.content);
            }
        }
    }
}

function handleCallApiEvent(updateValue, assistantMessageDiv) {
    // Handle API call events - these are typically internal processing events
    // that don't need UI updates, but we can log them for debugging
    if (typeof updateValue === 'string') {
        // If it's a string, it might be a simple status message
        createToolCallElement(assistantMessageDiv, `🔧 API Call: ${updateValue}`);
    } else if (typeof updateValue === 'object') {
        // If it's an object, it might contain more detailed information
        const apiName = updateValue.name || updateValue.api_name || 'Unknown API';
        const status = updateValue.status || updateValue.result || 'Processing';
        createToolCallElement(assistantMessageDiv, `🔧 ${apiName}: ${status}`);
    } else {
        // Fallback for other types
        createToolCallElement(assistantMessageDiv, `🔧 API Call: ${String(updateValue)}`);
    }
}

function createToolCallElement(assistantMessageDiv, text) {
    const toolCallDiv = document.createElement('div');
    toolCallDiv.className = 'tool-call fade-in';
    toolCallDiv.textContent = text;
    assistantMessageDiv.appendChild(toolCallDiv);
    
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

function handleStreamingCompletion(hasReceivedEvents, assistantMessageDiv) {
    if (!hasReceivedEvents) {
        assistantMessageDiv.textContent = '⚡ Cached response (no streaming events received)';
        assistantMessageDiv.style.fontStyle = 'italic';
        assistantMessageDiv.style.color = '#6b7280';
    } else if (window.currentInterrupt) {
        Logger.info('Interrupt detected - not overriding UI with final content');
    } else if (getFullMessageContent().trim()) {
        updateMessageContent(assistantMessageDiv, getFullMessageContent());
    } else {
        assistantMessageDiv.textContent = '⚠️ Response incomplete - please try again';
        assistantMessageDiv.style.color = '#dc2626';
    }
}

export async function handleNonStreamingResponse(response, assistantMessageDiv) {
    try {
        // Check if response has content
        const responseText = await response.text();
        
        if (!responseText || responseText.trim() === '') {
            assistantMessageDiv.textContent = '⚠️ Empty response from server';
            return;
        }
        
        // Try to parse as JSON
        let result;
        try {
            result = JSON.parse(responseText);
        } catch (parseError) {
            assistantMessageDiv.textContent = '⚠️ Invalid response format from server';
            return;
        }
        
        if (result.output?.messages?.length > 0) {
            const lastAIMessage = findLastAIMessage(result.output.messages);
            
            if (lastAIMessage) {
                setFullMessageContent(lastAIMessage.content);
                updateMessageContent(assistantMessageDiv, lastAIMessage.content);
            } else {
                assistantMessageDiv.textContent = 'No AI response found';
            }
        } else {
            assistantMessageDiv.textContent = 'No response content received';
        }
    } catch (error) {
        ErrorHandler.handleParsingError(error, null, 'Non-streaming response parsing');
    }
}

function findLastAIMessage(messages) {
    for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].type === MESSAGE_TYPES.AI && messages[i].content) {
            return messages[i];
        }
    }
    return null;
}
