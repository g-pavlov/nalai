/**
 * Streaming Module
 * Handles streaming and non-streaming response processing
 * 
 * Event Types:
 * - UPDATE EVENTS (response.update): Mark completion of workflow stages/nodes
 *   - Track progress and show workflow completion status
 *   - Do NOT affect content streaming
 * 
 * - OUTPUT EVENTS (response.output_text.delta): Stream actual LLM content
 *   - Handle content replacement and streaming
 *   - Clear intermediate task content when transitioning to LLM output
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
    // New: Accumulate tool call definitions from SSE deltas
    accumulatingToolCalls: new Map(), // tool_call_id -> { name, arguments, function_call }
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
    // Distinguish between UPDATE events (workflow stages) and OUTPUT events (content streaming)
    if (eventData.event) {
        const eventType = eventData.event;
        
        switch (eventType) {
            case 'response.created':
                handleResponseCreated(eventData, assistantMessageDiv);
                break;
            // OUTPUT EVENTS: Stream actual LLM content
            case 'response.output_text.delta':
                handleOutputTextDelta(eventData, assistantMessageDiv);
                break;
            case 'response.output_text.complete':
                handleOutputTextComplete(eventData, assistantMessageDiv);
                break;
            case 'response.output_tool_calls.delta':
                handleOutputToolCallsDelta(eventData, assistantMessageDiv);
                break;
            case 'response.output_tool_calls.complete':
                // This event is not currently sent by the server, but we handle it if it comes
                handleOutputToolCallsComplete(eventData, assistantMessageDiv);
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
            // UPDATE EVENTS: Mark completion of workflow stages/nodes
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
        // Validate that it's a proper domain-prefixed ID
        if (/^conv_[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{10,}$/i.test(eventData.conversation)) {
            setCurrentThreadId(eventData.conversation);
            Logger.info('New conversation thread started from response.created event', { 
                conversationId: eventData.conversation
            });
        } else {
            Logger.warn('Invalid conversation ID format in response.created event', { conversationId: eventData.conversation });
        }
    }
    
    // Response created - initialize streaming state
    // Only reset if this is a new conversation, not a resume
    if (!window.currentInterrupt) {
        resetStreamingProgressState();
        Logger.info('Reset streaming state for new conversation');
    } else {
        Logger.info('Preserving streaming state during interrupt resume');
    }
    
    // Check if this is a resume scenario by looking for existing tool calls in the conversation
    // When resuming, we need to extract tool calls from conversation history since SSE deltas won't be re-sent
    if (eventData.conversation) {
        extractToolCallsFromConversationHistory(eventData.conversation);
    }
    
    Logger.info('Initialized streaming state for new response');
}

/**
 * Extract tool calls from conversation history when resuming
 * This is needed because SSE deltas are not re-sent for existing tool calls during resume
 * @param {string} conversationId - The conversation ID to extract tool calls from
 */
function extractToolCallsFromConversationHistory(conversationId) {
    try {
        // Get conversation history from the UI state or localStorage
        const conversationHistory = getConversationHistory(conversationId);
        
        if (!conversationHistory || !Array.isArray(conversationHistory)) {
            Logger.info('No conversation history found for tool call extraction', { conversationId });
            return;
        }
        
        Logger.info('Extracting tool calls from conversation history', { 
            conversationId, 
            historyLength: conversationHistory.length 
        });
        
        // Look for assistant messages with tool calls in the history
        for (const message of conversationHistory) {
            if (message.role === 'assistant' && message.tool_calls && Array.isArray(message.tool_calls)) {
                for (const toolCall of message.tool_calls) {
                    if (toolCall.id && toolCall.name) {
                        // Create accumulated tool call entry from history
                        const accumulatedToolCall = {
                            id: toolCall.id,
                            name: toolCall.name,
                            arguments: '',
                            function_call: {
                                name: toolCall.name,
                                arguments: JSON.stringify(toolCall.args || {})
                            }
                        };
                        
                        streamingProgressState.accumulatingToolCalls.set(toolCall.id, accumulatedToolCall);
                        
                        Logger.info('Extracted tool call from conversation history', {
                            toolCallId: toolCall.id,
                            name: toolCall.name,
                            args: toolCall.args
                        });
                    }
                }
            }
        }
        
        Logger.info('Tool call extraction from conversation history completed', {
            conversationId,
            extractedCount: streamingProgressState.accumulatingToolCalls.size
        });
        
    } catch (error) {
        Logger.error('Error extracting tool calls from conversation history', {
            conversationId,
            error: error.message
        });
    }
}

/**
 * Get conversation history from UI state or localStorage
 * @param {string} conversationId - The conversation ID
 * @returns {Array|null} - Conversation history or null if not found
 */
function getConversationHistory(conversationId) {
    try {
        // Try to get from UI state first (if available)
        if (window.conversationHistory && window.conversationHistory[conversationId]) {
            return window.conversationHistory[conversationId];
        }
        
        // Fallback to localStorage if available
        const storedHistory = localStorage.getItem(`conversation_${conversationId}`);
        if (storedHistory) {
            return JSON.parse(storedHistory);
        }
        
        return null;
    } catch (error) {
        Logger.warn('Error getting conversation history', { conversationId, error: error.message });
        return null;
    }
}

function handleOutputTextDelta(eventData, assistantMessageDiv) {
    Logger.info('Output text delta received', { eventData });
    
    if (eventData.content) {
        const currentContent = getFullMessageContent();
        
        // OUTPUT EVENT: This is actual LLM content streaming
        // If we have intermediate task output (from update events), clear it when we start receiving real LLM content
        if (currentContent.includes('{"selected_apis":[]}') && 
            !eventData.content.includes('{"selected_apis":[]}') &&
            eventData.content.trim().length > 0) {
            
            Logger.info('OUTPUT EVENT: Clearing intermediate task content for real LLM output', {
                currentContentPreview: currentContent.substring(0, 100),
                newContentPreview: eventData.content.substring(0, 100)
            });
            
            // Clear the accumulated content and start fresh with LLM output
            setFullMessageContent('');
            
            // Clear the streaming content container
            const streamingContent = assistantMessageDiv.querySelector('.streaming-content');
            if (streamingContent) {
                streamingContent.innerHTML = '';
                Logger.info('Cleared streaming content container for LLM output transition');
            }
            
            // Start with the new LLM content
            setFullMessageContent(eventData.content);
            updateStreamingContent(assistantMessageDiv, eventData.content);
        } else {
            // Normal case - append to existing content
            const newContent = currentContent + eventData.content;
            
            Logger.info('OUTPUT EVENT: Appending LLM content', {
                deltaContent: eventData.content,
                newContentLength: newContent.length
            });
            
            setFullMessageContent(newContent);
            
            // Update streaming content in real-time
            updateStreamingContent(assistantMessageDiv, newContent);
        }
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
    
    // DO NOT add tool calls indicator here if there's an active interrupt
    // The indicator should only appear after response.tool events are received
    if (window.currentInterrupt) {
        Logger.info('Interrupt active - skipping tool calls indicator in response completed', { 
            toolCallsCount: streamingProgressState.toolCalls?.length || 0
        });
    } else {
        // Only add tool calls indicator for non-interrupted flows
        if (streamingProgressState.toolCalls && streamingProgressState.toolCalls.length > 0) {
            const deduplicatedToolCalls = deduplicateToolCalls(streamingProgressState.toolCalls);
            addToolCallsIndicatorToMessage(
                assistantMessageDiv, 
                deduplicatedToolCalls.length, 
                deduplicatedToolCalls
            );
            Logger.info('Added tool calls indicator from response completed (non-interrupted flow)', { 
                originalCount: streamingProgressState.toolCalls.length,
                deduplicatedCount: deduplicatedToolCalls.length
            });
        }
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
    const eventArgs = eventData.args; // ✅ NEW: Extract args from tool event
    
    if (!toolCallId || !toolName) {
        Logger.warn('Missing required tool event fields', { eventData });
        return;
    }
    
    // Get args from tool event first (enhanced approach), then fall back to accumulated data
    let args = {};
    let accumulatedToolCall = null;
    
    // ✅ NEW: Use args from tool event if available (this includes edited args from interrupts)
    if (eventArgs && typeof eventArgs === 'object') {
        args = eventArgs;
        Logger.info('Using args from tool event', { toolCallId, args });
    } else if (streamingProgressState.accumulatingToolCalls && streamingProgressState.accumulatingToolCalls.has(toolCallId)) {
        // Fallback to accumulated tool calls (legacy approach)
        accumulatedToolCall = streamingProgressState.accumulatingToolCalls.get(toolCallId);
        
        // Parse the accumulated arguments JSON
        if (accumulatedToolCall.function_call && accumulatedToolCall.function_call.arguments) {
            try {
                args = JSON.parse(accumulatedToolCall.function_call.arguments);
            } catch (parseError) {
                Logger.warn('Failed to parse accumulated tool call arguments', {
                    toolCallId,
                    arguments: accumulatedToolCall.function_call.arguments,
                    error: parseError.message
                });
                args = { raw_arguments: accumulatedToolCall.function_call.arguments };
            }
        } else if (accumulatedToolCall.args) {
            // Use args directly if available (from output_tool_calls.complete event)
            args = accumulatedToolCall.args;
        }
        
        Logger.info('Found accumulated tool call data', {
            toolCallId,
            accumulatedName: accumulatedToolCall.name,
            args: args
        });
    } else {
        // Fallback: Get args from pending tool calls if available
        if (streamingProgressState.pendingToolCalls && streamingProgressState.pendingToolCalls.has(toolCallId)) {
            const pendingInfo = streamingProgressState.pendingToolCalls.get(toolCallId);
            args = pendingInfo.args || {};
            Logger.info('Using fallback pending tool call args', { toolCallId, args });
        }
    }
    
    // Use the name from accumulated data if available, otherwise use the tool event name
    const finalToolName = accumulatedToolCall?.name || toolName;
    
    // Check if we already have a tool call with this ID in the main array
    let existingToolCallIndex = -1;
    if (streamingProgressState.toolCalls) {
        existingToolCallIndex = streamingProgressState.toolCalls.findIndex(tc => tc.tool_call_id === toolCallId);
        Logger.info('Checking for existing tool call', {
            toolCallId,
            toolCallsCount: streamingProgressState.toolCalls.length,
            existingToolCallIndex,
            toolCallIds: streamingProgressState.toolCalls.map(tc => tc.tool_call_id)
        });
    }
    
    if (existingToolCallIndex >= 0) {
        // Update existing tool call with results from response.tool event
        const existingToolCall = streamingProgressState.toolCalls[existingToolCallIndex];
        existingToolCall.content = content;
        existingToolCall.status = status;
        existingToolCall.timestamp = new Date().toISOString();
        
        // Preserve the args from the original tool call (don't overwrite with empty args)
        if (!existingToolCall.args || Object.keys(existingToolCall.args).length === 0) {
            existingToolCall.args = args;
        }
        
        Logger.info('Updated existing tool call with response.tool results', {
            toolCallId,
            name: existingToolCall.name,
            status: status,
            contentLength: content?.length || 0,
            args: existingToolCall.args
        });
        
        // Update the tool call display in the UI
        displayToolCallInStreamingContent(assistantMessageDiv, existingToolCall);
        
    } else {
        // Create new tool call object for tracking
        const toolCall = {
            name: finalToolName,
            content: content,
            status: status,
            tool_call_id: toolCallId,
            args: args,
            timestamp: new Date().toISOString(),
            source: 'response.tool'
        };
        
        // Add to streaming progress state (avoid duplicates)
        if (!toolCallExists(toolCall)) {
            streamingProgressState.toolCalls.push(toolCall);
            Logger.info('Added new tool call to streaming state', { 
                toolName: toolCall.name, 
                toolCallId: toolCall.tool_call_id,
                args: toolCall.args
            });
        } else {
            Logger.info('Tool call already exists in streaming state, skipping', { 
                toolName: toolCall.name, 
                toolCallId: toolCall.tool_call_id 
            });
        }
        
        // Display tool call in streaming content
        displayToolCallInStreamingContent(assistantMessageDiv, toolCall);
    }
    
    // Remove from pending calls if present
    if (streamingProgressState.pendingToolCalls && streamingProgressState.pendingToolCalls.has(toolCallId)) {
        streamingProgressState.pendingToolCalls.delete(toolCallId);
    }
    
    // Check if this is the first response.tool event - if so, add the tool calls indicator
    const existingIndicator = assistantMessageDiv.querySelector('.message-tools-indicator');
    if (!existingIndicator && streamingProgressState.toolCalls.length > 0) {
        const deduplicatedToolCalls = deduplicateToolCalls(streamingProgressState.toolCalls);
        addToolCallsIndicatorToMessage(
            assistantMessageDiv, 
            deduplicatedToolCalls.length, 
            deduplicatedToolCalls
        );
        Logger.info('Added tool calls indicator on first response.tool event', { 
            toolCallsCount: streamingProgressState.toolCalls.length,
            deduplicatedCount: deduplicatedToolCalls.length
        });
    }
    
    // Update streaming UI
    updateStreamingUI(assistantMessageDiv);
    
    Logger.info('Processed tool event', { 
        toolName: finalToolName, 
        status, 
        toolCallId,
        contentLength: content?.length || 0,
        args: args,
        updatedExisting: existingToolCallIndex >= 0
    });
}

function handleUpdateEvent(eventData, assistantMessageDiv) {
    Logger.info('UPDATE EVENT: Workflow stage completion received', { eventData });
    
    const task = eventData.task;
    const messages = eventData.messages || [];
    
    Logger.info('UPDATE EVENT: Processing workflow stage completion', { task, messageCount: messages.length });
    
    // UPDATE EVENT: This marks completion of a workflow stage/node
    // We track progress but don't affect content streaming - that's handled by output events
    
    // Create node log entry for the task
    const nodeLog = {
        node: task,
        displayName: NODE_COMPLETED_NAMES[task] || task,
        status: 'completed',
        timestamp: new Date().toISOString(),
        output: { task, messages }
    };
    
    Logger.info('UPDATE EVENT: Created workflow stage log entry', {
        task: task,
        outputPreview: JSON.stringify({ task, messages }).substring(0, 200)
    });
    
    streamingProgressState.nodeLogs.push(nodeLog);
    streamingProgressState.currentNode = task;
    
    // Clear streaming content when moving to a new node (except for the first node)
    // Only clear content for intermediate nodes, not for the final call_model node
    if (streamingProgressState.nodeLogs.length > 1) {
        const streamingContent = assistantMessageDiv.querySelector('.streaming-content');
        if (streamingContent) {
            const hasRealContent = streamingContent.textContent.trim().length > 0 && 
                                 !streamingContent.textContent.includes('{"selected_apis":[]}');
            
            if (task !== 'call_model') {
                streamingContent.innerHTML = '';
                Logger.info('Cleared streaming content for intermediate node transition', { 
                    previousNode: streamingProgressState.nodeLogs[streamingProgressState.nodeLogs.length - 2]?.node,
                    currentNode: task
                });
            } else if (task === 'call_model' && hasRealContent) {
                Logger.info('Preserved streaming content for call_model transition', { 
                    previousNode: streamingProgressState.nodeLogs[streamingProgressState.nodeLogs.length - 2]?.node,
                    currentNode: task,
                    contentLength: streamingContent.textContent.length
                });
            } else if (task === 'call_model' && !hasRealContent) {
                Logger.info('No real content to preserve for call_model transition', { 
                    previousNode: streamingProgressState.nodeLogs[streamingProgressState.nodeLogs.length - 2]?.node,
                    currentNode: task,
                    contentPreview: streamingContent.textContent.substring(0, 50)
                });
            }
        }
    }
    
    // Process any messages in the update
    if (messages && Array.isArray(messages)) {
        for (const message of messages) {
            Logger.info('Processing message in update event', { 
                messageType: message.type, 
                hasContent: !!message.content,
                content: typeof message.content === 'string' ? message.content?.substring(0, 100) : JSON.stringify(message.content).substring(0, 100) // Log first 100 chars
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
    
    // UPDATE EVENT: Update progress UI to show workflow stage completion
    updateStreamingUI(assistantMessageDiv);
    
    Logger.info('UPDATE EVENT: Workflow stage completion processed', { task, messageCount: messages.length });
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
    const contentPreview = typeof message.content === 'string' ? message.content?.substring(0, 50) : JSON.stringify(message.content).substring(0, 50);
    const toolMessageKey = message.tool_call_id || `${toolName}_${contentPreview}`;
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
    // The interrupts field contains a list of interrupt objects
    const interrupts = eventData.interrupts || [];
    if (interrupts.length === 0) {
        Logger.error('No interrupts found in SSE interrupt event', { eventData });
        return;
    }
    
    // Use the first interrupt (assuming single interrupt for now)
    const interrupt = interrupts[0];
    const actionRequest = interrupt.action_request || {};
    const action = actionRequest.action;
    const args = actionRequest.args || {};
    const config = interrupt.config || {};
    const description = interrupt.description || '';
    
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
    
    // Capture tool call arguments from interrupt data and get the tool_call_id
    const capturedToolCall = captureToolCall(action, args, 'interrupt');
    const toolCallId = capturedToolCall ? capturedToolCall.id : null;
    
    // Add call model response message for interrupted tool calls
    const streamingContent = assistantMessageDiv.querySelector('.streaming-content');
    if (streamingContent) {
        const callModelResponse = document.createElement('div');
        callModelResponse.className = 'call-model-response';
        callModelResponse.textContent = 'AI processed the request and identified tool calls that require human review.';
        streamingContent.appendChild(callModelResponse);
        Logger.info('Added call model response for interrupted tool call', { 
            toolCallId: toolCallId,
            action: action 
        });
    }
    
    // Create interrupt UI with the SSE format
    const actionRequestObj = { action, args };
    const interruptInfoWithConfig = {
        config: config,
        description: description
    };
    createInterruptUI(assistantMessageDiv, actionRequestObj, interruptInfoWithConfig);
    
    // Store the complete interrupt data for later use
    window.currentInterrupt = {
        value: {
            tool_call_id: toolCallId,
            action_request: actionRequest,
            config: config,
            description: description
        },
        resumable: true, // SSE interrupts are always resumable
        ns: 'interrupt'
    };
    
    Logger.info('SSE interrupt event processed', { 
        toolCallId: toolCallId,
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
        // New: Reset accumulating tool calls
        accumulatingToolCalls: new Map(),
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

function handleOutputToolCallsDelta(eventData, assistantMessageDiv) {
    Logger.info('Output tool calls delta received', { eventData });
    
    if (eventData.tool_calls && eventData.tool_calls.length > 0) {
        // Process each tool call delta to accumulate the complete tool call definition
        eventData.tool_calls.forEach(toolCallDelta => {
            const toolCallId = toolCallDelta.id;
            
            if (!toolCallId) {
                Logger.warn('Tool call delta missing ID', { toolCallDelta });
                return;
            }
            
            // Get or create accumulating tool call
            if (!streamingProgressState.accumulatingToolCalls.has(toolCallId)) {
                streamingProgressState.accumulatingToolCalls.set(toolCallId, {
                    id: toolCallId,
                    name: '',
                    arguments: '',
                    function_call: {}
                });
            }
            
            const accumulatingToolCall = streamingProgressState.accumulatingToolCalls.get(toolCallId);
            
            // Accumulate name if present
            if (toolCallDelta.name) {
                accumulatingToolCall.name = toolCallDelta.name;
            }
            
            // Accumulate function call data if present
            if (toolCallDelta.function_call) {
                if (toolCallDelta.function_call.name) {
                    accumulatingToolCall.function_call.name = toolCallDelta.function_call.name;
                }
                if (toolCallDelta.function_call.arguments) {
                    accumulatingToolCall.function_call.arguments = 
                        (accumulatingToolCall.function_call.arguments || '') + toolCallDelta.function_call.arguments;
                }
            }
            
            // Update the name from function_call.name if available
            if (accumulatingToolCall.function_call.name) {
                accumulatingToolCall.name = accumulatingToolCall.function_call.name;
            }
            
            Logger.info('Accumulated tool call delta', {
                toolCallId,
                name: accumulatingToolCall.name,
                argumentsLength: accumulatingToolCall.function_call.arguments?.length || 0,
                functionCall: accumulatingToolCall.function_call
            });
        });
        
        // Capture the last tool call ID for interrupt handling
        const lastToolCall = eventData.tool_calls[eventData.tool_calls.length - 1];
        if (lastToolCall && lastToolCall.id) {
            streamingProgressState.lastToolCall = lastToolCall;
        }
        
        Logger.info('Tool calls delta processed', { 
            toolCallsCount: eventData.tool_calls.length,
            totalAccumulatingCount: streamingProgressState.accumulatingToolCalls.size,
            lastToolCallId: streamingProgressState.lastToolCall?.id
        });
    }
}

function handleOutputToolCallsComplete(eventData, assistantMessageDiv) {
    Logger.info('Output tool calls complete received', { eventData });
    
    // Process tool calls from the complete event (before interrupt)
    const completedToolCalls = [];
    
    if (eventData.tool_calls && Array.isArray(eventData.tool_calls)) {
        // Process tool calls directly from the complete event
        eventData.tool_calls.forEach(toolCall => {
            try {
                const toolCallId = toolCall.id;
                const toolName = toolCall.name;
                const args = toolCall.args || {};
                
                if (!toolCallId || !toolName) {
                    Logger.warn('Tool call missing required fields', { toolCall });
                    return;
                }
                
                const completedToolCall = {
                    id: toolCallId,
                    name: toolName,
                    args: args,
                    tool_call_id: toolCallId,
                    timestamp: new Date().toISOString(),
                    source: 'output_tool_calls_complete',
                    status: 'pending', // Will be updated when response.tool event arrives
                    content: null // Will be populated when response.tool event arrives
                };
                
                completedToolCalls.push(completedToolCall);
                
                // Store in accumulating tool calls for later matching with response.tool events
                streamingProgressState.accumulatingToolCalls.set(toolCallId, {
                    id: toolCallId,
                    name: toolName,
                    args: args,
                    function_call: {
                        name: toolName,
                        arguments: JSON.stringify(args)
                    }
                });
                
                Logger.info('Completed tool call from complete event', {
                    toolCallId,
                    name: completedToolCall.name,
                    args: completedToolCall.args
                });
                
            } catch (error) {
                Logger.error('Error processing tool call from complete event', {
                    toolCall,
                    error: error.message
                });
            }
        });
    } else {
        // Fallback: Process accumulated tool calls from delta events
        for (const [toolCallId, accumulatingToolCall] of streamingProgressState.accumulatingToolCalls.entries()) {
            try {
                // Parse the accumulated arguments JSON
                let args = {};
                if (accumulatingToolCall.function_call.arguments) {
                    try {
                        args = JSON.parse(accumulatingToolCall.function_call.arguments);
                    } catch (parseError) {
                        Logger.warn('Failed to parse tool call arguments', {
                            toolCallId,
                            arguments: accumulatingToolCall.function_call.arguments,
                            error: parseError.message
                        });
                        args = { raw_arguments: accumulatingToolCall.function_call.arguments };
                    }
                }
                
                const completedToolCall = {
                    id: toolCallId,
                    name: accumulatingToolCall.name || 'Unknown tool',
                    args: args,
                    tool_call_id: toolCallId,
                    timestamp: new Date().toISOString(),
                    source: 'output_tool_calls_complete_accumulated',
                    status: 'pending',
                    content: null
                };
                
                completedToolCalls.push(completedToolCall);
                
                Logger.info('Completed tool call from accumulated data', {
                    toolCallId,
                    name: completedToolCall.name,
                    args: completedToolCall.args
                });
                
            } catch (error) {
                Logger.error('Error processing completed tool call', {
                    toolCallId,
                    error: error.message,
                    accumulatingToolCall
                });
            }
        }
    }
    
    // Add completed tool calls to the main toolCalls array
    streamingProgressState.toolCalls.push(...completedToolCalls);
    
    // DO NOT add tool calls indicator here - wait for response.tool events
    // The indicator will be added when the first response.tool event is received
    Logger.info('Tool calls complete - stored for later display when response.tool events arrive', { 
        completedCount: completedToolCalls.length
    });
}

