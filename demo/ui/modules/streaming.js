/**
 * Streaming Module
 * Handles streaming and non-streaming response processing
 */

import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { DOM } from './dom.js';
import { updateMessageContent, cleanupMessageProcessing } from './messages.js';
import { setFullMessageContent, getFullMessageContent, getCurrentThreadId, setCurrentThreadId } from './state.js';
import { Validator } from './validator.js';
import { createInterruptUI } from './interrupts.js';
import { addToolCallsIndicatorToMessage } from './toolCalls.js';

// Check JSON format setting directly from DOM
function isJsonFormatEnabled() {
    const toggle = document.getElementById('jsonFormatToggle');
    return toggle ? toggle.checked : false;
}

// Streaming state for real-time progress
let streamingProgressState = {
    currentNode: null,
    nodeLogs: [],
    toolCalls: [],
    pendingToolCalls: new Map(),
    toolCallCounter: 0,
    finalMessage: null,
    isComplete: false
};

// Node mapping for completed status
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
    
    // Initialize streaming state
    Logger.info('Starting streaming response');
    
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
                        const eventData = JSON.parse(data);
                        hasReceivedEvents = true;
                        
                        // Process the event data directly
                        processStreamEvent(eventData, assistantMessageDiv);
                        
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

export function processStreamEvent(eventData, assistantMessageDiv) {
    Logger.info('Processing stream event', { eventData });
    
    // Handle SSE events with exact model from sse_serializer.py
    if (eventData.event) {
        const eventType = eventData.event;
        
        switch (eventType) {
            case 'response.created':
                handleResponseCreated(eventData, assistantMessageDiv);
                break;
            case 'response.output_text.delta':
                handleOutputTextDelta(eventData, assistantMessageDiv);
                break;
            case 'response.output_text.complete':
                handleOutputTextComplete(eventData, assistantMessageDiv);
                break;
            case 'response.tool_calls.delta':
                // Skip progressive tool call events - we only show completed tool calls
                Logger.info('Skipping progressive tool call delta event', { eventData });
                break;
            case 'response.tool_calls.complete':
                handleToolCallsComplete(eventData, assistantMessageDiv);
                break;
            case 'response.interrupt':
                handleInterruptEvent(eventData, assistantMessageDiv);
                break;
            case 'response.resumed':
                Logger.info('Response resumed event received', { eventData });
                break;
            case 'response.completed':
                handleResponseCompleted(eventData, assistantMessageDiv);
                break;
            case 'response.error':
                handleErrorEvent(eventData, assistantMessageDiv);
                break;
            case 'response.tool':
                handleToolEvent(eventData, assistantMessageDiv);
                break;
            case 'response.update':
                handleUpdateEvent(eventData, assistantMessageDiv);
                break;
            default:
                Logger.warn('Unknown SSE event type', { eventType, eventData });
        }
        return;
    }
    
    Logger.warn('Unexpected event format - missing event field', { eventData });
}

function handleResponseCreated(eventData, assistantMessageDiv) {
    Logger.info('Response created event received', { eventData });
    
    // Handle conversation ID from event data if present
    if (eventData.conversation && eventData.conversation !== getCurrentThreadId()) {
        // Validate that it's a proper UUID
        if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(eventData.conversation)) {
            setCurrentThreadId(eventData.conversation);
            Logger.info('New conversation thread started from response.created event', { 
                conversationId: eventData.conversation
            });
        } else {
            Logger.warn('Invalid conversation ID format in response.created event', { conversationId: eventData.conversation });
        }
    }
    
    // Response created - initialize streaming state
    resetStreamingProgressState();
    Logger.info('Initialized streaming state for new response');
}

function handleOutputTextDelta(eventData, assistantMessageDiv) {
    Logger.info('Output text delta received', { eventData });
    
    if (eventData.content) {
        const currentContent = getFullMessageContent();
        const newContent = currentContent + eventData.content;
        
        Logger.info('Text delta received', {
            deltaContent: eventData.content,
            newContentLength: newContent.length
        });
        
        setFullMessageContent(newContent);
        
        // Update streaming content in real-time
        updateStreamingContent(assistantMessageDiv, newContent);
    }
}

function handleOutputTextComplete(eventData, assistantMessageDiv) {
    Logger.info('Output text complete received', { eventData });
    
    if (eventData.content) {
        // Set the complete content and update the UI
        setFullMessageContent(eventData.content);
        updateStreamingContent(assistantMessageDiv, eventData.content);
        
        Logger.info('Text content completed', {
            contentLength: eventData.content.length,
            contentPreview: eventData.content.substring(0, 100)
        });
    }
    
    // Clear accumulated content state after completing a text stream
    // This ensures clean separation between different content streams
    setFullMessageContent('');
    Logger.info('Cleared accumulated content after text complete event');
}



function handleToolCallsComplete(eventData, assistantMessageDiv) {
    Logger.info('Tool calls complete received', { eventData });
    
    if (eventData.tool_calls && Array.isArray(eventData.tool_calls)) {
        eventData.tool_calls.forEach(toolCall => {
            captureToolCall(
                toolCall.name || 'Unknown tool',
                toolCall.args || {},
                'tool_calls_complete'
            );
        });
    }
}

function handleResponseCompleted(eventData, assistantMessageDiv) {
    Logger.info('Response completed event received', { eventData });
    
    streamingProgressState.isComplete = true;
    
    // Add tool calls indicator if there are tool calls
    if (streamingProgressState.toolCalls && streamingProgressState.toolCalls.length > 0) {
        const deduplicatedToolCalls = deduplicateToolCalls(streamingProgressState.toolCalls);
        addToolCallsIndicatorToMessage(
            assistantMessageDiv, 
            deduplicatedToolCalls.length, 
            deduplicatedToolCalls
        );
        Logger.info('Added tool calls indicator from response completed', { 
            originalCount: streamingProgressState.toolCalls.length,
            deduplicatedCount: deduplicatedToolCalls.length
        });
    }
    
    // Clean up streaming UI
    const progressContainer = assistantMessageDiv.querySelector('.streaming-progress');
    if (progressContainer) {
        progressContainer.remove();
    }
}

function handleErrorEvent(eventData, assistantMessageDiv) {
    Logger.error('Error event received from server', { eventData });
    
    let errorMessage = 'An error occurred while processing your request.';
    
    // Extract error message from SSE error event format
    if (eventData.error) {
        errorMessage = eventData.error;
    } else if (eventData.detail) {
        errorMessage = eventData.detail;
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

function handleToolEvent(eventData, assistantMessageDiv) {
    Logger.info('Tool event received', { eventData });
    
    // Extract tool information from SSE format
    const toolCallId = eventData.tool_call_id;
    const toolName = eventData.tool_name;
    const status = eventData.status;
    const content = eventData.content;
    
    if (!toolCallId || !toolName) {
        Logger.warn('Missing required tool event fields', { eventData });
        return;
    }
    
    // Get args from pending tool calls if available
    let args = {};
    if (streamingProgressState.pendingToolCalls && streamingProgressState.pendingToolCalls.has(toolCallId)) {
        const pendingInfo = streamingProgressState.pendingToolCalls.get(toolCallId);
        args = pendingInfo.args || {};
    }
    
    // Create tool call object for tracking
    const toolCall = {
        name: toolName,
        content: content,
        status: status,
        tool_call_id: toolCallId,
        args: args, // Include args for proper deduplication
        timestamp: new Date().toISOString()
    };
    
    // Add to streaming progress state (avoid duplicates)
    if (!toolCallExists(toolCall)) {
        streamingProgressState.toolCalls.push(toolCall);
        Logger.info('Added tool call to streaming state', { 
            toolName: toolCall.name, 
            toolCallId: toolCall.tool_call_id 
        });
    } else {
        Logger.info('Tool call already exists in streaming state, skipping', { 
            toolName: toolCall.name, 
            toolCallId: toolCall.tool_call_id 
        });
    }
    
    // Remove from pending calls if present
    if (streamingProgressState.pendingToolCalls && streamingProgressState.pendingToolCalls.has(toolCallId)) {
        streamingProgressState.pendingToolCalls.delete(toolCallId);
    }
    
    // Display tool call in streaming content
    displayToolCallInStreamingContent(assistantMessageDiv, toolCall);
    
    // Update streaming UI
    updateStreamingUI(assistantMessageDiv);
    
    Logger.info('Processed tool event', { 
        toolName, 
        status, 
        toolCallId,
        contentLength: content?.length || 0
    });
}

function handleUpdateEvent(eventData, assistantMessageDiv) {
    Logger.info('Update event received', { eventData });
    
    const task = eventData.task;
    const messages = eventData.messages || [];
    
    Logger.info('Processing SSE update event', { task, messageCount: messages.length });
    
    // Create node log entry for the task
    const nodeLog = {
        node: task,
        displayName: NODE_COMPLETED_NAMES[task] || task,
        status: 'completed',
        timestamp: new Date().toISOString(),
        output: { task, messages }
    };
    
    Logger.info('Created node log entry', {
        task: task,
        outputPreview: JSON.stringify({ task, messages }).substring(0, 200)
    });
    
    streamingProgressState.nodeLogs.push(nodeLog);
    streamingProgressState.currentNode = task;
    
    // Process any messages in the update
    if (messages && Array.isArray(messages)) {
        for (const message of messages) {
            Logger.info('Processing message in update event', { 
                messageType: message.type, 
                hasContent: !!message.content,
                content: message.content?.substring(0, 100) // Log first 100 chars
            });
            
            // Handle different message types
            // Note: We don't process tool calls from update events as they contain conversation history
            // Tool calls are processed from specific response.tool events instead
            if (message.type === 'tool' && message.content) {
                // Skip tool messages from update events - they're from conversation history
                Logger.info('Skipping tool message from update event (conversation history)', { 
                    toolCallId: message.tool_call_id 
                });
            } else if (message.type === 'ai' && message.tool_calls && Array.isArray(message.tool_calls)) {
                // Skip AI tool calls from update events - they're from conversation history
                Logger.info('Skipping AI tool calls from update event (conversation history)', { 
                    toolCallCount: message.tool_calls.length 
                });
            }
            

        }
    }
    
    // Update streaming UI to show progress
    updateStreamingUI(assistantMessageDiv);
    
    Logger.info('SSE update event processed', { task, messageCount: messages.length });
}

/**
 * Find the tool name by looking up the tool call ID in various sources
 * @param {string} toolCallId - The ID of the tool call to look up
 * @param {Array} messages - Current messages array to search in
 * @param {Object} streamingState - Current streaming state with tool calls
 * @returns {string} The tool name or 'Unknown tool' if not found
 */
function findToolNameByCallId(toolCallId, messages, streamingState) {
    // Look for the tool call in the current messages
    for (const msg of messages) {
        if (msg.type === 'ai' && msg.tool_calls) {
            for (const toolCall of msg.tool_calls) {
                if (toolCall.id === toolCallId) {
                    return toolCall.name;
                }
            }
        }
    }
    
    // If not found in current messages, check streaming state
    for (const existingToolCall of streamingState.toolCalls) {
        if (existingToolCall.id === toolCallId) {
            return existingToolCall.name;
        }
    }
    
    // If still not found, check global tool calls state
    const globalToolCalls = State.getToolCalls();
    for (const globalToolCall of globalToolCalls) {
        if (globalToolCall.id === toolCallId) {
            return globalToolCall.name;
        }
    }
    
    return 'Unknown tool';
}

/**
 * Handle tool messages from update events
 * @param {Object} message - The tool message object
 * @param {Array} messages - All messages in the current update
 * @param {HTMLElement} assistantMessageDiv - The assistant message container
 */
function handleToolMessage(message, messages, assistantMessageDiv) {
    // Find the corresponding tool call to get the correct name
    const toolName = findToolNameByCallId(message.tool_call_id, messages, streamingProgressState);
    
    // Check if this tool message has already been processed
    const toolMessageKey = message.tool_call_id || `${toolName}_${message.content?.substring(0, 50)}`;
    if (streamingProgressState.processedToolCalls && streamingProgressState.processedToolCalls.has(toolMessageKey)) {
        Logger.info('Tool message already processed, skipping', {
            toolName: toolName,
            toolCallId: message.tool_call_id,
            key: toolMessageKey
        });
        return;
    }
    
    // Mark this tool message as processed
    if (!streamingProgressState.processedToolCalls) {
        streamingProgressState.processedToolCalls = new Set();
    }
    streamingProgressState.processedToolCalls.add(toolMessageKey);
    
    // Create tool call from message
    const toolCall = {
        name: toolName,
        content: message.content,
        tool_call_id: message.tool_call_id || `tool_${Date.now()}`,
        id: message.tool_call_id,
        timestamp: new Date().toISOString()
    };
    
    // Add to streaming progress state (avoid duplicates)
    if (!toolCallExists(toolCall)) {
        streamingProgressState.toolCalls.push(toolCall);
        Logger.info('Added tool call from tool message to streaming state', { 
            toolName: toolCall.name, 
            toolCallId: toolCall.tool_call_id 
        });
    } else {
        Logger.info('Tool call from tool message already exists in streaming state, skipping', { 
            toolName: toolCall.name, 
            toolCallId: toolCall.tool_call_id 
        });
    }
    displayToolCallInStreamingContent(assistantMessageDiv, toolCall);
}

/**
 * Handle AI messages that contain tool calls
 * @param {Object} message - The AI message object with tool calls
 * @param {HTMLElement} assistantMessageDiv - The assistant message container
 */
function handleAIMessageWithToolCalls(message, assistantMessageDiv) {
    // Extract tool calls from AI message
    // Don't clear progressive content - let it build up
    message.tool_calls.forEach(toolCall => {
        if (toolCall.name && toolCall.name !== 'Unknown tool') {
            const toolCallObj = {
                name: toolCall.name,
                args: toolCall.args || {},
                id: toolCall.id || `tool_${Date.now()}`,
                tool_call_id: toolCall.id, // Store the tool_call_id for proper deduplication
                timestamp: new Date().toISOString()
            };
            
            // Check if this tool call has already been processed in this update event
            const toolCallKey = toolCall.id || `${toolCall.name}_${JSON.stringify(toolCall.args || {})}`;
            if (streamingProgressState.processedToolCalls && streamingProgressState.processedToolCalls.has(toolCallKey)) {
                Logger.info('Tool call already processed in this update event, skipping', {
                    name: toolCall.name,
                    id: toolCall.id,
                    key: toolCallKey
                });
                return;
            }
            
            // Mark this tool call as processed
            if (!streamingProgressState.processedToolCalls) {
                streamingProgressState.processedToolCalls = new Set();
            }
            streamingProgressState.processedToolCalls.add(toolCallKey);
            
            // Capture the tool call
            captureToolCall(toolCall.name, toolCall.args || {}, 'update_event');
            
            // Add to streaming state (avoid duplicates)
            if (!toolCallExists(toolCallObj)) {
                streamingProgressState.toolCalls.push(toolCallObj);
                Logger.info('Added tool call from AI message to streaming state', { 
                    toolName: toolCallObj.name, 
                    toolCallId: toolCallObj.id 
                });
            } else {
                Logger.info('Tool call from AI message already exists in streaming state, skipping', { 
                    toolName: toolCallObj.name, 
                    toolCallId: toolCallObj.id 
                });
            }
            
            Logger.info('Processed complete tool call from update event', {
                name: toolCall.name,
                args: toolCall.args
            });
        }
    });
}



function handleInterruptEvent(eventData, assistantMessageDiv) {
    Logger.info('Interrupt detected', { eventData });
    
    // Clear content state when interrupt occurs
    setFullMessageContent('');
    Logger.info('Cleared content state for interrupt');
    
    // Keep processing state active during interrupt - don't clear it
    Logger.info('Maintaining processing state during interrupt');
    
    // Extract information from SSE interrupt format
    const interruptId = eventData.interrupt_id;
    const action = eventData.action;
    const args = eventData.args || {};
    const config = eventData.config || {};
    const description = eventData.description || '';
    
    if (!action) {
        Logger.error('Missing action in SSE interrupt event', { eventData });
        return;
    }
    
    // Update input field placeholder to indicate tool call decision is needed
    let placeholderText = 'Waiting for tool call decision...';
    if (description) {
        placeholderText = `Waiting for decision: ${description}`;
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
    captureToolCall(action, args, 'interrupt');
    
    // Create interrupt UI with the SSE format
    const actionRequestObj = { action, args };
    const interruptInfoWithConfig = {
        config: config,
        description: description
    };
    createInterruptUI(assistantMessageDiv, actionRequestObj, interruptInfoWithConfig);
    
    window.currentInterrupt = {
        value: {
            tool_call_id: interruptId,
            action: action,
            args: args,
            action_request: { action, args },
            config: config,
            description: description
        },
        resumable: true, // SSE interrupts are always resumable
        ns: 'interrupt'
    };
    
    Logger.info('SSE interrupt event processed', { 
        interruptId, 
        action, 
        args, 
        description 
    });
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



function displayToolCallInStreamingContent(assistantMessageDiv, toolCall) {
    Logger.info('Displaying tool call in streaming content', { 
        toolName: toolCall.name,
        toolCall: toolCall
    });
    
    // Don't display tool calls in streaming content - they should only be in the tools panel
    // This prevents tool calls from replacing the final response
    Logger.info('Skipping tool call display in streaming content - will be shown in tools panel', { 
        toolName: toolCall.name 
    });
    
}

// Helper function to capture tool call arguments from any source
export function captureToolCall(name, args, source = 'unknown') {
    if (!name) return null;
    
    // Store tool call info for later use when we get the tool response
    if (!streamingProgressState.pendingToolCalls) {
        streamingProgressState.pendingToolCalls = new Map();
    }
    
    // Check if we already have a tool call with the same name and arguments
    // This prevents duplicate tool calls from being created
    for (const [id, existingInfo] of streamingProgressState.pendingToolCalls.entries()) {
        if (existingInfo.name === name && JSON.stringify(existingInfo.args) === JSON.stringify(args || {})) {
            Logger.info(`Tool call already exists in pending calls, skipping duplicate`, { 
                name: name, 
                args: args,
                existingId: id,
                source: source
            });
            return existingInfo;
        }
    }
    
    // Also check if we already have this tool call in the main toolCalls array
    for (const existingToolCall of streamingProgressState.toolCalls) {
        if (existingToolCall.name === name && JSON.stringify(existingToolCall.args || {}) === JSON.stringify(args || {})) {
            Logger.info(`Tool call already exists in main array, skipping duplicate`, { 
                name: name, 
                args: args,
                existingId: existingToolCall.id,
                source: source
            });
            return existingToolCall;
        }
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
    
    // Skip progressive delta events since we're not showing them
    if (source === 'progressive_delta') {
        Logger.info('Skipping progressive delta tool call capture', { name, args });
        return null;
    }
    
    const toolCallInfo = {
        name: name,
        args: args || {},
        id: `tool_${streamingProgressState.toolCallCounter++}_${Date.now()}`,
        source: source,
        timestamp: new Date().toISOString()
    };
    
    streamingProgressState.pendingToolCalls.set(toolCallInfo.id, toolCallInfo);
    
    Logger.info(`Captured tool call from ${source}`, { 
        name: toolCallInfo.name, 
        args: toolCallInfo.args,
        id: toolCallInfo.id,
        fullToolCallInfo: toolCallInfo
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

/**
 * Check if a tool call already exists in the streaming state
 * @param {Object} toolCall - The tool call object to check
 * @returns {boolean} - Whether the tool call already exists
 */
function toolCallExists(toolCall) {
    if (!toolCall || !toolCall.name) return false;
    
    // Check by tool_call_id first (most reliable)
    if (toolCall.tool_call_id) {
        return streamingProgressState.toolCalls.some(existing => 
            existing.tool_call_id === toolCall.tool_call_id
        );
    }
    
    // Check by name and arguments (more thorough comparison)
    return streamingProgressState.toolCalls.some(existing => {
        if (existing.name !== toolCall.name) return false;
        
        // Compare arguments more carefully
        const existingArgs = existing.args || {};
        const newArgs = toolCall.args || {};
        
        // If both have no arguments, they're the same
        if (Object.keys(existingArgs).length === 0 && Object.keys(newArgs).length === 0) {
            return true;
        }
        
        // If one has arguments and the other doesn't, they're different
        if (Object.keys(existingArgs).length === 0 || Object.keys(newArgs).length === 0) {
            return false;
        }
        
        // Compare arguments by JSON stringification
        return JSON.stringify(existingArgs) === JSON.stringify(newArgs);
    });
}

/**
 * Deduplicate tool calls array to remove any duplicates
 * @param {Array} toolCalls - Array of tool call objects
 * @returns {Array} - Deduplicated array of tool calls
 */
function deduplicateToolCalls(toolCalls) {
    if (!Array.isArray(toolCalls)) return [];
    
    const seen = new Set();
    const deduplicated = [];
    
    for (const toolCall of toolCalls) {
        if (!toolCall || !toolCall.name) continue;
        
        // Create a unique key for this tool call
        let key;
        if (toolCall.tool_call_id) {
            key = `id:${toolCall.tool_call_id}`;
        } else {
            // For tool calls without tool_call_id, use name + args as key
            const argsKey = JSON.stringify(toolCall.args || {});
            key = `name:${toolCall.name}:args:${argsKey}`;
        }
        
        if (!seen.has(key)) {
            seen.add(key);
            deduplicated.push(toolCall);
        } else {
            Logger.info('Removed duplicate tool call during deduplication', { 
                name: toolCall.name, 
                toolCallId: toolCall.tool_call_id,
                key: key
            });
        }
    }
    
    // Additional check: if we have multiple tool calls with the same name and args but different IDs,
    // keep only the first one
    const finalDeduplicated = [];
    const nameArgsSeen = new Set();
    
    for (const toolCall of deduplicated) {
        const nameArgsKey = `${toolCall.name}:${JSON.stringify(toolCall.args || {})}`;
        
        if (!nameArgsSeen.has(nameArgsKey)) {
            nameArgsSeen.add(nameArgsKey);
            finalDeduplicated.push(toolCall);
        } else {
            Logger.info('Removed duplicate tool call by name+args during final deduplication', { 
                name: toolCall.name, 
                toolCallId: toolCall.tool_call_id,
                nameArgsKey: nameArgsKey
            });
        }
    }
    
    return finalDeduplicated;
}

export function resetStreamingProgressState() {
    streamingProgressState = {
        currentNode: null,
        nodeLogs: [],
        toolCalls: [],
        pendingToolCalls: new Map(),
        processedToolCalls: new Set(),
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
            const deduplicatedToolCalls = deduplicateToolCalls(streamingProgressState.toolCalls);
            addToolCallsIndicatorToMessage(
                assistantMessageDiv, 
                deduplicatedToolCalls.length, 
                deduplicatedToolCalls
            );
            Logger.info('Added tool calls indicator from streaming completion', { 
                originalCount: streamingProgressState.toolCalls.length,
                deduplicatedCount: deduplicatedToolCalls.length
            });
        }
    } else {
        assistantMessageDiv.textContent = 'Response incomplete - please try again';
        assistantMessageDiv.style.color = '#dc2626';
    }
}

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
        
        // Handle new response format with output array
        if (result.output && Array.isArray(result.output)) {
            const assistantMessages = result.output.filter(msg => msg.role === 'assistant');
            
            if (assistantMessages.length > 0) {
                const lastAssistantMessage = assistantMessages[assistantMessages.length - 1];
                
                if (lastAssistantMessage.content && lastAssistantMessage.content.length > 0) {
                    // Extract text content from content blocks
                    let textContent = '';
                    for (const contentBlock of lastAssistantMessage.content) {
                        if (contentBlock.type === 'text') {
                            textContent += contentBlock.text;
                        }
                    }
                    
                    if (textContent) {
                        setFullMessageContent(textContent);
                        updateMessageContent(assistantMessageDiv, textContent);
                    } else {
                        assistantMessageDiv.textContent = 'No text content found in assistant message';
                    }
                } else {
                    assistantMessageDiv.textContent = 'No content found in assistant message';
                }
            } else {
                assistantMessageDiv.textContent = 'No assistant messages found';
            }
        } else {
            assistantMessageDiv.textContent = 'No response content received';
        }
    } catch (error) {
        ErrorHandler.handleParsingError(error, null, 'Non-streaming response parsing');
    }
}

