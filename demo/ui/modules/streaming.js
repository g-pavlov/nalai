/**
 * Streaming Module
 * Handles streaming and non-streaming response processing
 */

import { EVENT_TYPES, MESSAGE_TYPES } from './config.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { DOM } from './dom.js';
import { updateMessageContent, cleanupMessageProcessing } from './messages.js';
import { setFullMessageContent, getFullMessageContent } from './state.js';
import { Validator } from './validator.js';
import { createInterruptUI } from './interrupts.js';
import { addToolCallsIndicatorToMessage } from './toolCalls.js';
// Check JSON format setting directly from DOM
function isJsonFormatEnabled() {
    const toggle = document.getElementById('jsonFormatToggle');
    return toggle ? toggle.checked : false;
}

// Streaming state for real-time progress (separate from debug state)
let streamingProgressState = {
    currentNode: null,
    nodeLogs: [],
    toolCalls: [],
    pendingToolCalls: new Map(),
    toolCallCounter: 0, // Counter for generating unique IDs
    finalMessage: null,
    isComplete: false
};

// Node mapping for human-readable names (current/active status)
const NODE_DISPLAY_NAMES = {
    'call_model': 'AI processing',
    'call_api': 'Tool calling',
    'check_cache': 'Checking cache',
    'load_api_summaries': 'Loading API summaries',
    'load_api_specs': 'Loading API specifications',
    'select_relevant_apis': 'AI selecting APIs'
};

// Node mapping for completed status (past tense for update events)
const NODE_COMPLETED_NAMES = {
    'call_model': 'AI processed',
    'call_api': 'Tool called',
    'check_cache': 'Cache checked',
    'load_api_summaries': 'API summaries loaded',
    'load_api_specs': 'API specifications loaded',
    'select_relevant_apis': 'APIs selected'
};

export async function handleStreamingResponse(response, assistantMessageDiv) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let hasReceivedEvents = false;
    let buffer = '';
    
    // Clear any existing content state at the start of streaming
    setFullMessageContent('');
    Logger.info('Cleared content state at start of streaming');
    
    // Initialize streaming progress state
    resetStreamingProgressState();
    

    
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
    Logger.info('Processing message events', { messageCount: eventData.length });
    
    for (const message of eventData) {
        Logger.info('Processing message', {
            type: message.type,
            hasContent: !!message.content,
            contentLength: message.content?.length || 0,
            id: message.id,
            langgraphNode: message.langgraph_node
        });
        
        // Handle AIMessageChunk for real-time streaming
        if (message.type === MESSAGE_TYPES.AI_CHUNK && message.content) {
            handleAIMessageChunk(message, assistantMessageDiv);
        } else if (message.type === MESSAGE_TYPES.AI && message.content) {
            handleAIMessage(message, assistantMessageDiv);
        } else if (message.type === MESSAGE_TYPES.TOOL && message.content) {
            handleToolMessage(message, assistantMessageDiv);
        }
    }
}

function handleAIMessageChunk(message, assistantMessageDiv) {
    const currentContent = getFullMessageContent();
    const newContent = currentContent + message.content;
    setFullMessageContent(newContent);
    
    // Update streaming progress to show "AI processing..." during real-time streaming
    const progressContainer = assistantMessageDiv.querySelector('.streaming-progress');
    if (progressContainer) {
        const progressTitle = progressContainer.querySelector('.progress-title');
        if (progressTitle) {
            progressTitle.textContent = 'AI processing';
        }
    }
    
    // Update the streaming content in real-time
    updateStreamingContent(assistantMessageDiv, newContent);
    

    
    Logger.info('Updated content with chunk', { 
        chunk: message.content, 
        fullLength: newContent.length 
    });
}

function handleAIMessage(message, assistantMessageDiv) {
    // For complete AI messages, replace the content entirely
    const newContent = message.content;
    setFullMessageContent(newContent);
    streamingProgressState.finalMessage = newContent;
    
    // Capture tool calls if present
    Logger.info('Checking for tool calls in AI message', {
        hasToolCalls: !!message.tool_calls,
        toolCallsType: typeof message.tool_calls,
        toolCallsLength: message.tool_calls?.length || 0
    });
    
    if (message.tool_calls && Array.isArray(message.tool_calls)) {
        message.tool_calls.forEach(toolCall => {
            captureToolCall(
                toolCall.name || 'Unknown tool',
                toolCall.args || {},
                'ai_message'
            );
        });
    } else if (message.tool_calls) {
        Logger.info('Tool calls present but not array', { toolCalls: message.tool_calls });
    }
    
    // Update streaming content (this will replace any existing content)
    updateStreamingContent(assistantMessageDiv, newContent);
    

    
    Logger.info('Set final AI message', { 
        length: newContent.length 
    });
}

function handleToolMessage(message, assistantMessageDiv) {
    // Debug logging to see what we're receiving
    Logger.info('Processing tool message', {
        name: message.name,
        tool_call_id: message.tool_call_id,
        contentLength: message.content?.length || 0,
        pendingToolCallsSize: streamingProgressState.pendingToolCalls?.size || 0
    });
    
    // Try to find matching pending tool call by tool_call_id first
    let toolCallInfo = null;
    if (streamingProgressState.pendingToolCalls && message.tool_call_id) {
        toolCallInfo = streamingProgressState.pendingToolCalls.get(message.tool_call_id);
        Logger.info('Tool call matching by ID result', {
            tool_call_id: message.tool_call_id,
            found: !!toolCallInfo,
            toolCallInfo: toolCallInfo
        });
    }
    
    // If no match by ID, try to find by name
    if (!toolCallInfo && streamingProgressState.pendingToolCalls) {
        for (const [id, info] of streamingProgressState.pendingToolCalls.entries()) {
            if (info.name === message.name) {
                toolCallInfo = info;
                Logger.info('Found tool call by name match', {
                    name: message.name,
                    id: id,
                    args: info.args
                });
                break;
            }
        }
    }
    
    // If still no match, try to find any pending tool call (for cases where names might not match exactly)
    if (!toolCallInfo && streamingProgressState.pendingToolCalls && streamingProgressState.pendingToolCalls.size > 0) {
        // Get the most recent tool call
        const entries = Array.from(streamingProgressState.pendingToolCalls.entries());
        const [id, info] = entries[entries.length - 1];
        toolCallInfo = info;
        Logger.info('Using most recent pending tool call as fallback', {
            toolName: message.name,
            pendingName: info.name,
            id: id,
            args: info.args
        });
    }
    
    // If we still don't have tool call info, create a placeholder
    if (!toolCallInfo) {
        Logger.warn('No matching tool call found for tool message', {
            toolName: message.name,
            toolCallId: message.tool_call_id,
            pendingToolCallsCount: streamingProgressState.pendingToolCalls?.size || 0
        });
    }
    
    const toolCall = {
        name: message.name || 'Unknown tool',
        content: message.content,
        args: toolCallInfo ? toolCallInfo.args : {},
        response: message.content, // Store the response content
        source: toolCallInfo ? toolCallInfo.source : 'unknown',
        timestamp: new Date().toISOString()
    };
    
    // Check if this tool call was from an interrupt flow and update status
    if (toolCallInfo && toolCallInfo.source === 'interrupt') {
        // Check if the tool call was confirmed or rejected
        if (toolCallInfo.confirmed === false) {
            toolCall.confirmed = false;
            toolCall.response = 'User rejected the tool call';
        } else if (toolCallInfo.confirmed === true) {
            toolCall.confirmed = true;
        }
    }
    
    streamingProgressState.toolCalls.push(toolCall);
    
    // Remove from pending calls if found
    if (toolCallInfo && streamingProgressState.pendingToolCalls) {
        const keyToDelete = message.tool_call_id || Array.from(streamingProgressState.pendingToolCalls.keys()).find(id => 
            streamingProgressState.pendingToolCalls.get(id).name === message.name
        );
        if (keyToDelete) {
            streamingProgressState.pendingToolCalls.delete(keyToDelete);
        }
    }
    

    
    // Display tool call in streaming content
    displayToolCallInStreamingContent(assistantMessageDiv, toolCall);
    
    // Update streaming UI to show tool call
    updateStreamingUI(assistantMessageDiv);
    
    Logger.info('Added tool call', { 
        name: message.name, 
        contentLength: message.content?.length || 0,
        hasArgs: !!toolCallInfo,
        args: toolCallInfo?.args
    });
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
                handleNodeUpdate(updateKey, updateValue, assistantMessageDiv);
                break;
            default:
                Logger.warn('Unknown update key', { updateKey, updateValue });
        }
    }
}

function handleNodeUpdate(nodeName, updateValue, assistantMessageDiv) {
    // Clear content state when a new node starts (except for call_model which produces content)
    if (nodeName !== 'call_model') {
        setFullMessageContent('');
        Logger.info('Cleared content state for new node', { nodeName });
    }
    
    const nodeLog = {
        node: nodeName,
        displayName: NODE_COMPLETED_NAMES[nodeName] || nodeName,
        status: 'completed',
        timestamp: new Date().toISOString(),
        output: updateValue
    };
    
    streamingProgressState.nodeLogs.push(nodeLog);
    streamingProgressState.currentNode = nodeName;
    
    // Update streaming UI to show progress
    updateStreamingUI(assistantMessageDiv);
    

    
    Logger.info('Node completed', { nodeName });
}

function handleCallModelEvent(updateValue, assistantMessageDiv) {
    const nodeLog = {
        node: 'call_model',
        displayName: NODE_COMPLETED_NAMES['call_model'],
        status: 'completed',
        timestamp: new Date().toISOString(),
        output: updateValue
    };
    
    streamingProgressState.nodeLogs.push(nodeLog);
    streamingProgressState.currentNode = 'call_model';
    
    // Update streaming UI to show progress
    updateStreamingUI(assistantMessageDiv);
    

    
    Logger.info('Call model completed', { updateValue });
}

function handleCallApiEvent(updateValue, assistantMessageDiv) {
    // Debug logging to see what's in the updateValue
    Logger.info('Call API event received', { 
        updateValue,
        updateValueType: typeof updateValue,
        isArray: Array.isArray(updateValue),
        keys: updateValue && typeof updateValue === 'object' ? Object.keys(updateValue) : null
    });
    
    // Try to extract tool call information from updateValue
    if (updateValue && typeof updateValue === 'object') {
        // Look for tool call information in various possible locations
        let toolCallInfo = null;
        
        // Check if updateValue contains tool call data directly
        if (updateValue.tool_name || updateValue.name) {
            toolCallInfo = {
                name: updateValue.tool_name || updateValue.name,
                args: updateValue.args || updateValue.arguments || {},
                id: updateValue.tool_call_id || updateValue.id || `api_${Date.now()}`,
                timestamp: new Date().toISOString()
            };
        }
        // Check if updateValue contains a tool call object
        else if (updateValue.tool_call) {
            toolCallInfo = {
                name: updateValue.tool_call.name || updateValue.tool_call.tool_name,
                args: updateValue.tool_call.args || updateValue.tool_call.arguments || {},
                id: updateValue.tool_call.id || updateValue.tool_call.tool_call_id || `api_${Date.now()}`,
                timestamp: new Date().toISOString()
            };
        }
        // Check if updateValue is an array and contains tool call info
        else if (Array.isArray(updateValue) && updateValue.length > 0) {
            const firstItem = updateValue[0];
            if (firstItem && typeof firstItem === 'object') {
                toolCallInfo = {
                    name: firstItem.tool_name || firstItem.name || 'Unknown tool',
                    args: firstItem.args || firstItem.arguments || {},
                    id: firstItem.tool_call_id || firstItem.id || `api_${Date.now()}`,
                    timestamp: new Date().toISOString()
                };
            }
        }
        
        // Store tool call info if found
        if (toolCallInfo) {
            captureToolCall(
                toolCallInfo.name,
                toolCallInfo.args,
                'api_event'
            );
        }
    }
    
    const nodeLog = {
        node: 'call_api',
        displayName: NODE_COMPLETED_NAMES['call_api'],
        status: 'completed',
        timestamp: new Date().toISOString(),
        output: updateValue
    };
    
    streamingProgressState.nodeLogs.push(nodeLog);
    streamingProgressState.currentNode = 'call_api';
    
    // Update streaming UI to show progress
    updateStreamingUI(assistantMessageDiv);
    

    
    Logger.info('API call completed', { updateValue });
}

function updateStreamingUI(assistantMessageDiv) {
    // Create or update the streaming progress container
    let progressContainer = assistantMessageDiv.querySelector('.streaming-progress');
    if (!progressContainer) {
        progressContainer = createStreamingProgressContainer(assistantMessageDiv);
    }
    
    // Update the progress title with current node name
    const progressTitle = progressContainer.querySelector('.progress-title');
    if (progressTitle && streamingProgressState.currentNode) {
        const currentNode = streamingProgressState.nodeLogs[streamingProgressState.nodeLogs.length - 1];
        if (currentNode) {
            progressTitle.textContent = currentNode.displayName;
        }
    }
    
    // Ensure progress dots are visible during streaming
    const progressDots = progressContainer.querySelector('.progress-dots');
    if (progressDots) {
        progressDots.style.display = 'inline';
    }
    
    // Note: Tool calls are now handled in the final completion stage
    // and displayed in the collapsible tool panel
    
    // Scroll to bottom
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

function updateStreamingContent(assistantMessageDiv, content) {
    // Check if there's an interrupt UI that should be cleared first
    const interruptContainer = assistantMessageDiv.querySelector('.interrupt-container');
    if (interruptContainer) {
        interruptContainer.remove();
        Logger.info('Removed interrupt UI to restore streaming content');
    }
    
    // Create or update the streaming content container
    let contentContainer = assistantMessageDiv.querySelector('.streaming-content');
    if (!contentContainer) {
        contentContainer = createStreamingContentContainer(assistantMessageDiv);
    }
    
    // Clear any existing content and update with new content
    contentContainer.innerHTML = '';
    
    // Update the content
    try {
        contentContainer.innerHTML = marked.parse(content);
    } catch (error) {
        contentContainer.textContent = content;
    }
    
    // Only remove progress dots if streaming is not complete
    if (!streamingProgressState.isComplete) {
        const progressContainer = assistantMessageDiv.querySelector('.streaming-progress');
        if (progressContainer) {
            const progressDots = progressContainer.querySelector('.progress-dots');
            if (progressDots) {
                progressDots.style.display = 'none';
            }
        }
    }
    
    // Scroll to bottom
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }
}

function createStreamingProgressContainer(assistantMessageDiv) {
    const progressContainer = document.createElement('div');
    progressContainer.className = 'streaming-progress';
    progressContainer.innerHTML = `
        <div class="progress-header">
            <span class="progress-title">Starting...</span>
            <span class="progress-dots">...</span>
        </div>
    `;
    
    assistantMessageDiv.appendChild(progressContainer);
    return progressContainer;
}

function createStreamingContentContainer(assistantMessageDiv) {
    const contentContainer = document.createElement('div');
    contentContainer.className = 'streaming-content';
    
    assistantMessageDiv.appendChild(contentContainer);
    return contentContainer;
}

/**
 * Displays a tool call in the streaming content container
 * @param {HTMLElement} assistantMessageDiv - The assistant message container
 * @param {Object} toolCall - The tool call object
 */
function displayToolCallInStreamingContent(assistantMessageDiv, toolCall) {
    // Create or get the streaming content container
    let contentContainer = assistantMessageDiv.querySelector('.streaming-content');
    if (!contentContainer) {
        contentContainer = createStreamingContentContainer(assistantMessageDiv);
    }
    
    // Clear previous content for non-interrupt tool calls to avoid prepending
    if (toolCall.source !== 'interrupt') {
        contentContainer.innerHTML = '';
        Logger.info('Cleared streaming content for non-interrupt tool call', { toolName: toolCall.name });
    }
    
    // Create tool call element using the same structure as tool-call-item
    const toolCallElement = document.createElement('div');
    toolCallElement.className = 'tool-call-item';
    
    // Format the tool call display
    const toolName = toolCall.name;
    const args = toolCall.args;
    const response = toolCall.response;
    
    // Determine status based on tool call source and confirmation
    let status = 'completed';
    let statusClass = 'completed';
    if (toolCall.source === 'interrupt') {
        if (toolCall.confirmed === false) {
            status = 'rejected';
            statusClass = 'rejected';
        } else if (toolCall.confirmed === true) {
            status = 'confirmed';
            statusClass = 'confirmed';
        }
    }
    
    // Create the tool call HTML using the same structure as the example
    let toolCallHTML = `
        <div class="tool-call-header">
            <div class="tool-call-name">${toolName}</div>
            <div class="tool-call-status ${statusClass}">${status}</div>
        </div>
    `;
    
    // Add arguments if available
    if (args && Object.keys(args).length > 0) {
        toolCallHTML += `
            <div class="tool-call-section">
                <div class="tool-call-section-title">Arguments</div>
                <div class="tool-call-args">${JSON.stringify(args, null, 2)}</div>
            </div>
        `;
    }
    
    // Add response if available
    if (response) {
        toolCallHTML += `
            <div class="tool-call-section">
                <div class="tool-call-section-title">Response</div>
                <div class="tool-call-response">${typeof response === 'string' ? response : JSON.stringify(response, null, 2)}</div>
            </div>
        `;
    }
    
    toolCallElement.innerHTML = toolCallHTML;
    
    // Add to content container
    contentContainer.appendChild(toolCallElement);
    
    Logger.info('Displayed tool call in streaming content', { 
        toolName: toolCall.name,
        hasArgs: !!args,
        hasResponse: !!response,
        status: status
    });
}



function createStreamingToolElement(tool) {
    const toolElement = document.createElement('div');
    toolElement.className = 'tool-item';
    
    // Safely format the tool content
    const formattedContent = formatToolContent(tool.content);
    
    // Format arguments if available
    let argsSection = '';
    if (tool.args && Object.keys(tool.args).length > 0) {
        const formattedArgs = formatToolContent(JSON.stringify(tool.args));
        argsSection = `
            <div class="tool-args">
                <div class="tool-args-header">Arguments:</div>
                <div class="tool-args-content">${formattedArgs}</div>
            </div>
        `;
    }
    
    toolElement.innerHTML = `
        <div class="tool-header">
            <span class="tool-icon">⚙</span>
            <span class="tool-name">${tool.name}</span>
        </div>
        ${argsSection}
        <div class="tool-content">
            <div class="tool-content-header">Response:</div>
            <div class="tool-content-body">${formattedContent}</div>
        </div>
    `;
    
    return toolElement;
}

function formatToolContent(content) {
    if (!content || typeof content !== 'string') {
        return content || '';
    }
    
    // Try to parse as JSON and pretty print it
    try {
        const parsed = JSON.parse(content);
        return `<pre class="json-content">${JSON.stringify(parsed, null, 2)}</pre>`;
    } catch (error) {
        // If it's not valid JSON, return as plain text
        return `<span class="text-content">${escapeHtml(content)}</span>`;
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Helper function to capture tool call arguments from any source
export function captureToolCall(name, args, source = 'unknown') {
    if (!name) return null;
    
    const toolCallInfo = {
        name: name,
        args: args || {},
        id: `tool_${streamingProgressState.toolCallCounter++}_${Date.now()}`,
        source: source,
        timestamp: new Date().toISOString()
    };
    
    // Store tool call info for later use when we get the tool response
    if (!streamingProgressState.pendingToolCalls) {
        streamingProgressState.pendingToolCalls = new Map();
    }
    
    // If this is an edited tool call, replace any existing tool call with the same name
    if (source === 'interrupt_edit') {
        // Find and remove any existing tool call with the same name
        for (const [id, existingInfo] of streamingProgressState.pendingToolCalls.entries()) {
            if (existingInfo.name === name) {
                streamingProgressState.pendingToolCalls.delete(id);
                Logger.info('Replaced existing tool call with edited version', {
                    name: name,
                    oldArgs: existingInfo.args,
                    newArgs: args
                });
                break;
            }
        }
    }
    
    streamingProgressState.pendingToolCalls.set(toolCallInfo.id, toolCallInfo);
    
    Logger.info(`Captured tool call from ${source}`, { 
        name: toolCallInfo.name, 
        args: toolCallInfo.args,
        id: toolCallInfo.id
    });
    
    return toolCallInfo;
}

/**
 * Updates the status of a tool call based on interrupt decision
 * @param {string} toolName - Name of the tool
 * @param {string} decision - Decision made (accept, reject, edit)
 */
export function updateToolCallStatus(toolName, decision) {
    // Find the tool call in the toolCalls array and update its status
    for (const toolCall of streamingProgressState.toolCalls) {
        if (toolCall.name === toolName) {
            if (decision === 'accept') {
                toolCall.confirmed = true;
            } else if (decision === 'reject') {
                toolCall.confirmed = false;
            } else if (decision === 'edit') {
                toolCall.confirmed = true; // Edited calls are considered confirmed
            }
            Logger.info('Updated tool call status', { toolName, decision, confirmed: toolCall.confirmed });
            break;
        }
    }
    
    // Also update any pending tool calls
    if (streamingProgressState.pendingToolCalls) {
        for (const [id, toolCallInfo] of streamingProgressState.pendingToolCalls.entries()) {
            if (toolCallInfo.name === toolName) {
                if (decision === 'accept') {
                    toolCallInfo.confirmed = true;
                } else if (decision === 'reject') {
                    toolCallInfo.confirmed = false;
                } else if (decision === 'edit') {
                    toolCallInfo.confirmed = true;
                }
                Logger.info('Updated pending tool call status', { toolName, decision, confirmed: toolCallInfo.confirmed });
                break;
            }
        }
    }
}

function resetStreamingProgressState() {
    streamingProgressState = {
        currentNode: null,
        nodeLogs: [],
        toolCalls: [],
        pendingToolCalls: new Map(),
        toolCallCounter: 0,
        finalMessage: null,
        isComplete: false
    };
}

export function resetStreamingStateAfterInterrupt() {
    // Clear the full message content state to prevent duplication
    setFullMessageContent('');
    
    Logger.info('Streaming content state reset after interrupt completion');
}



function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
}

export function handleStreamingCompletion(hasReceivedEvents, assistantMessageDiv) {
    streamingProgressState.isComplete = true;
    
    Logger.info('handleStreamingCompletion called', { hasReceivedEvents, hasInterrupt: !!window.currentInterrupt });
    
    // Add a visual indicator that the function was called
    if (assistantMessageDiv) {
        assistantMessageDiv.setAttribute('data-completion-handled', 'true');
    }
    
    if (!hasReceivedEvents) {
        assistantMessageDiv.textContent = 'Cached response (no streaming events received)';
        assistantMessageDiv.style.fontStyle = 'italic';
        assistantMessageDiv.style.color = '#6b7280';
        return;
    }
    
    if (window.currentInterrupt) {
        Logger.info('Interrupt detected - not overriding UI with final content');
        return;
    }
    
    // Standard completion - reorganize the UI
    const progressContainer = assistantMessageDiv.querySelector('.streaming-progress');
    Logger.info('Progress container found', { hasProgressContainer: !!progressContainer });
    
    if (progressContainer) {
        // Remove the progress header
        const progressHeader = progressContainer.querySelector('.progress-header');
        Logger.info('Progress header found', { hasProgressHeader: !!progressHeader });
        if (progressHeader) {
            progressHeader.remove();
            Logger.info('Progress header removed');
        }
        
        // Remove or hide the progress content container to save space
        const progressContent = progressContainer.querySelector('.progress-content');
        if (progressContent) {
            progressContent.remove();
            Logger.info('Progress content container removed');
        }
    }
    
    // Show final content - get from DOM since state might be cleared
    const streamingContent = assistantMessageDiv.querySelector('.streaming-content');
    let finalContent = '';
    
    if (streamingContent) {
        finalContent = streamingContent.textContent || streamingContent.innerText || '';
    } else {
        // Fallback to state if DOM doesn't have content
        finalContent = getFullMessageContent();
    }
    
    Logger.info('Final content check', { 
        hasStreamingContent: !!streamingContent, 
        contentLength: finalContent.length,
        contentPreview: finalContent.substring(0, 100)
    });
    
    if (finalContent.trim()) {
        // Content exists and is already in DOM - just ensure it's visible
        Logger.info('Final content confirmed, streaming content already displayed');
        
        // Add tool calls indicator if there are tool calls
        if (streamingProgressState.toolCalls && streamingProgressState.toolCalls.length > 0) {
            addToolCallsIndicatorToMessage(
                assistantMessageDiv, 
                streamingProgressState.toolCalls.length, 
                streamingProgressState.toolCalls
            );
            Logger.info('Added tool calls indicator', { 
                toolCount: streamingProgressState.toolCalls.length 
            });
        }
    } else {
        assistantMessageDiv.textContent = 'Response incomplete - please try again';
        assistantMessageDiv.style.color = '#dc2626';
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
        <div class="message-content-layout">
            <span class="message-icon">Error</span>
            <div>
                <strong>Server Error:</strong> ${errorMessage}
                <br>
                <small class="message-text-muted">Please try again or check your input.</small>
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
    
    // Clear processing state only if there's no active interrupt
    if (!window.currentInterrupt) {
        cleanupMessageProcessing();
    } else {
        Logger.info('Skipping cleanup during active interrupt');
    }
}

function handleInterruptEvent(updateValue, assistantMessageDiv) {
    Logger.info('Interrupt detected', { updateValue });
    
    // Clear content state when interrupt occurs
    setFullMessageContent('');
    Logger.info('Cleared content state for interrupt');
    
    // Keep processing state active during interrupt - don't clear it
    // The processing state should remain true until the entire workflow is complete
    Logger.info('Maintaining processing state during interrupt');
    
    // Parse interrupt data first
    const interruptObject = updateValue[0];
    const interruptInfo = interruptObject.value[0]; // Get the first interrupt from the value array
    const actionRequest = interruptInfo?.action_request || {};
    
    // Update input field placeholder to indicate tool call decision is needed
    const config = interruptInfo?.config || {};
    const allowAccept = config.allow_accept !== false;
    const allowEdit = config.allow_edit === true;
    const allowRespond = config.allow_respond === true;
    
    let placeholderText = 'Waiting for tool call decision...';
    if (allowAccept && allowEdit && allowRespond) {
        placeholderText = 'Please accept, edit, or reject the tool call above...';
    } else if (allowAccept && allowEdit) {
        placeholderText = 'Please accept or edit the tool call above...';
    } else if (allowAccept && allowRespond) {
        placeholderText = 'Please accept or reject the tool call above...';
    } else if (allowAccept) {
        placeholderText = 'Please accept the tool call above...';
    }
    
    DOM.messageInput.placeholder = placeholderText;
    
    // Update streaming progress to show "Tool calling..." status during interrupt
    const progressContainer = assistantMessageDiv.querySelector('.streaming-progress');
    if (progressContainer) {
        const progressTitle = progressContainer.querySelector('.progress-title');
        if (progressTitle) {
            progressTitle.textContent = 'Tool calling';
        }
    }
    
    // Capture tool call arguments from interrupt data
    if (actionRequest && actionRequest.action) {
        captureToolCall(
            actionRequest.action,
            actionRequest.args || {},
            'interrupt'
        );
    }
    
    createInterruptUI(assistantMessageDiv, actionRequest, interruptInfo);
    
    window.currentInterrupt = {
        value: interruptInfo,
        resumable: interruptObject.resumable,
        ns: interruptObject.ns
    };
}

// Removed parseInterruptString and parseInterruptFallback functions
// as they are no longer needed with proper JSON serialization

export async function handleNonStreamingResponse(response, assistantMessageDiv) {
    try {
        // Check if response has content
        const responseText = await response.text();
        
        if (!responseText || responseText.trim() === '') {
            assistantMessageDiv.textContent = 'Empty response from server';
            return;
        }
        
        // Try to parse as JSON
        let result;
        try {
            result = JSON.parse(responseText);
        } catch (parseError) {
            assistantMessageDiv.textContent = 'Invalid response format from server';
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

