/**
 * Response Processor
 * 
 * Handles processing of complete API responses by message type.
 * Provides the same rich experience as streaming responses but without dynamic progress.
 */

import { Logger } from './logger.js';
import { getCurrentThreadId, setCurrentThreadId } from './state.js';

// ============================================================================
// CONTROL LOGIC - Main orchestration functions
// ============================================================================

/**
 * Main entry point for processing complete responses with state machine
 */
export async function processCompleteResponseWithStateMachine(response, assistantMessageDiv) {
    try {
        const responseData = await response.json();
        
        Logger.info('Processing complete response with state machine', {
            hasStateMachine: !!assistantMessageDiv.stateMachine,
            responseData: JSON.stringify(responseData).substring(0, 200) + '...'
        });
        
        // Step 1: Handle conversation context
        await handleConversationContext(responseData);
        
        // Step 2: Process message output if available
        if (assistantMessageDiv.stateMachine && responseData.output) {
            await processMessageOutput(responseData.output, assistantMessageDiv.stateMachine);
        } else {
            Logger.warn('No state machine or output found for complete response');
        }

        // Step 3: Handle interrupts if present
        if (assistantMessageDiv.stateMachine && isInterruptedResponse(responseData)) {
            await handleInterrupts(responseData.interrupts, assistantMessageDiv.stateMachine);
        }
        
    } catch (error) {
        Logger.error('Error processing complete response', { error });
        throw error;
    }
}

// ============================================================================
// CONVERSATION CONTEXT HANDLER
// ============================================================================

/**
 * Handle conversation context updates from response
 */
async function handleConversationContext(responseData) {
    try {
        const respConvId = responseData.conversation_id;
        const currentThreadId = getCurrentThreadId();
        
        if (respConvId && respConvId !== currentThreadId) {
            setCurrentThreadId(respConvId);
            Logger.info('Thread ID updated from complete response body', {
                conversationId: respConvId
            });
        }
    } catch (e) {
        Logger.warn('Could not reconcile conversation_id from complete response', { error: e });
    }
}

// ============================================================================
// MESSAGE OUTPUT PROCESSOR
// ============================================================================

/**
 * Process the message output array
 */
async function processMessageOutput(output, stateMachine) {
    // Store the full output in the state machine for tool message processing
    stateMachine.currentOutput = output;
    
    const messagesToProcess = extractRelevantMessages(output);
    
    Logger.info('Processing message output', {
        totalMessages: output.length,
        messagesToProcess: messagesToProcess.length
    });
    
    // Process each message by type
    Logger.info('About to process messages', {
        messageCount: messagesToProcess.length,
        messageTypes: messagesToProcess.map(m => ({ role: m.role, finishReason: m.finish_reason, hasToolCalls: !!(m.tool_calls && m.tool_calls.length > 0) }))
    });
    
    for (const message of messagesToProcess) {
        Logger.info('Processing message', {
            role: message.role,
            messageId: message.id,
            finishReason: message.finish_reason,
            hasToolCalls: !!(message.tool_calls && message.tool_calls.length > 0),
            attachedToolCalls: !!(message._attachedToolCalls && message._attachedToolCalls.length > 0)
        });
        await processMessageByType(message, stateMachine);
    }
}

/**
 * Extract messages that should be processed (after last human message)
 * For non-streaming responses, we want only the final AI response and tool-related messages,
 * not intermediate AI messages that cause content duplication.
 */
function extractRelevantMessages(output) {
    let lastHumanMessageIndex = -1;
    for (let i = output.length - 1; i >= 0; i--) {
        if (output[i].role === 'user') {
            lastHumanMessageIndex = i;
            break;
        }
    }
    
    const messagesAfterHuman = output.slice(lastHumanMessageIndex + 1);
    
    // Trace back from the end to find only relevant messages:
    // 1. Last AI/interrupt message (finish_reason: "stop" or interrupt status)
    // 2. Tool messages
    // 3. Tool call message (role: assistant, finish_reason: "tool_call", tool_calls non-empty)
    
    const relevantMessages = [];
    let foundFinalResponse = false;
    let foundToolCallMessage = false;
    let toolCallsToProcess = []; // Store tool calls to process with final response
    
    // Process messages from end to beginning to find the final response first
    for (let i = messagesAfterHuman.length - 1; i >= 0; i--) {
        const message = messagesAfterHuman[i];
        
        if (message.role === 'tool') {
            // Always include tool messages
            relevantMessages.unshift(message);
        } else if (message.role === 'assistant' && !foundFinalResponse) {
            // Check if this is the final AI response
            if (message.finish_reason === 'stop' || 
                (!message.tool_calls || message.tool_calls.length === 0)) {
                // This is the final response - include it
                // If we found tool calls earlier, attach them to this message
                if (toolCallsToProcess.length > 0) {
                    message._attachedToolCalls = toolCallsToProcess;
                    Logger.info('Attached tool calls to final AI response', { 
                        toolCallCount: toolCallsToProcess.length 
                    });
                }
                
                relevantMessages.unshift(message);
                foundFinalResponse = true;
                Logger.info('Found final AI response message', { 
                    messageId: message.id, 
                    finishReason: message.finish_reason,
                    hasToolCalls: !!(message.tool_calls && message.tool_calls.length > 0),
                    attachedToolCalls: toolCallsToProcess.length
                });
            }
        } else if (message.role === 'assistant' && !foundToolCallMessage && 
                   message.finish_reason === 'tool_call' && 
                   message.tool_calls && message.tool_calls.length > 0) {
            // This is the tool call message - we'll process its tool calls but NOT include it as a separate message
            // The tool calls will be handled by the final AI response message
            Logger.info('Found tool call message - will process tool calls but not render separately', { 
                messageId: message.id, 
                finishReason: message.finish_reason,
                toolCallCount: message.tool_calls.length
            });
            
            // Store tool calls to process with the final response
            toolCallsToProcess = message.tool_calls;
            foundToolCallMessage = true;
        }
    }
    
    // Filter out any assistant messages that have no meaningful content
    // BUT preserve tool call messages even if they have no content
    const filteredMessages = relevantMessages.filter(message => {
        if (message.role === 'assistant') {
            const hasContent = message.content && 
                              Array.isArray(message.content) && 
                              message.content.some(block => block.type === 'text' && block.text && block.text.trim());
            
            const hasToolCalls = message.tool_calls && message.tool_calls.length > 0;
            
            // Keep messages with content OR tool calls
            if (!hasContent && !hasToolCalls) {
                Logger.info('Filtering out assistant message with no content and no tool calls', { 
                    messageId: message.id, 
                    finishReason: message.finish_reason,
                    hasToolCalls: hasToolCalls
                });
                return false;
            }
        }
        return true;
    });
    
    Logger.info('Filtered relevant messages', {
        beforeFilter: relevantMessages.length,
        afterFilter: filteredMessages.length,
        filteredOut: relevantMessages.length - filteredMessages.length
    });
    
    Logger.info('Extracted relevant messages for non-streaming processing', {
        totalMessages: output.length,
        messagesAfterHuman: messagesAfterHuman.length,
        relevantMessages: relevantMessages.length,
        foundFinalResponse: foundFinalResponse,
        foundToolCallMessage: foundToolCallMessage,
        toolMessageCount: relevantMessages.filter(m => m.role === 'tool').length,
        filteredMessages: filteredMessages.length
    });
    
    return filteredMessages;
}

/**
 * Route message to appropriate handler based on role
 */
async function processMessageByType(message, stateMachine) {
    try {
        switch (message.role) {
            case 'assistant':
                await processAssistantMessage(message, stateMachine);
                break;
            case 'tool':
                await processToolMessage(message, stateMachine);
                break;
            default:
                Logger.warn('Unknown message role', { role: message.role, messageId: message.id });
        }
    } catch (error) {
        Logger.error('Error processing message by type', { error, messageId: message.id, role: message.role });
    }
}

// ============================================================================
// MESSAGE TYPE HANDLERS
// ============================================================================

/**
 * Process assistant messages (AI responses, tool calls)
 */
async function processAssistantMessage(message, stateMachine) {
    // For tool call messages (finish_reason: "tool_call"), don't render content
    // as it's usually intermediate text like "I'll help you with that request"
    if (message.finish_reason === 'tool_call') {
        Logger.info('Processing tool call message - skipping content rendering', {
            messageId: message.id,
            contentPreview: extractTextContent(message.content).substring(0, 100) + '...'
        });
        
        // Only handle the tool calls, don't render the content
        if (message.tool_calls && message.tool_calls.length > 0) {
            await handleToolCalls(message.tool_calls, stateMachine, message.id);
        }
        return;
    }
    
    // For final AI responses, render the content
    const contentText = extractTextContent(message.content);
    if (contentText.trim()) {
        stateMachine.updateContentProgressive(contentText.trim());
    }
    
    // Handle tool calls if present (either from the message itself or attached from earlier)
    const allToolCalls = message.tool_calls || message._attachedToolCalls || [];
    if (allToolCalls.length > 0) {
        await handleToolCalls(allToolCalls, stateMachine, message.id);
    }
}

/**
 * Process tool messages (tool execution results)
 */
async function processToolMessage(message, stateMachine) {
    Logger.info('Processing tool message', { 
        toolCallId: message.tool_call_id,
        messageId: message.id,
        hasStatus: message.status !== undefined,
        hasToolName: message.tool_name !== undefined,
        hasArgs: message.args !== undefined,
        messageKeys: Object.keys(message)
    });
    
    const toolResult = extractTextContent(message.content);
    
    // Use centralized tool status logic from the state machine
    // The state machine will handle status determination based on interrupt decisions
    if (stateMachine.updateToolCall) {
        try {
            // Extract tool details from the prior AI message that contains the tool_calls
            // const toolDetails = extractToolDetailsFromPriorMessage(message.tool_call_id, stateMachine);
            
            const updateData = {
                content: toolResult,
                timestamp: new Date().toISOString(),
                source: 'response.tool'
            };
            
            // Add tool details if we found them
            if (message.tool_name) {
                updateData.name = message.tool_name;
            }
            if (message.args) {
                updateData.args = message.args;
            }
            
            // Handle status updates for non-streaming responses
            // Use the status from the message if provided
            if (message.status) {
                updateData.status = message.status;
                Logger.info('Using status from tool message', { 
                    toolCallId: message.tool_call_id,
                    status: message.status
                });
            }
            
            stateMachine.updateToolCall(message.tool_call_id, updateData);
            
            if (stateMachine.updateToolsDisplay) {
                stateMachine.updateToolsDisplay();
            }
        } catch (error) {
            Logger.error('Error updating tool results in state machine', { error, toolCallId: message.tool_call_id });
        }
    }
}

// ============================================================================
// INTERRUPT HANDLER
// ============================================================================

/**
 * Check if response indicates an interrupted flow
 */
function isInterruptedResponse(responseData) {
    return responseData.status === 'interrupted' && 
           Array.isArray(responseData.interrupts) && 
           responseData.interrupts.length > 0;
}

/**
 * Handle interrupts from complete response
 */
async function handleInterrupts(interrupts, stateMachine) {
    try {
        const transformedInterrupts = transformInterrupts(interrupts);
        
        Logger.info('Invoking interrupt dialog from complete response', {
            interruptCount: transformedInterrupts.length
        });

        stateMachine.showInterruptDialog({ interrupts: transformedInterrupts });
    } catch (e) {
        Logger.error('Failed to show interrupt dialog for complete response', { error: e });
    }
}

// ============================================================================
// DATA PROCESSORS - Utility functions for data extraction and transformation
// ============================================================================

/**
 * Extract text content from message content array
 */
function extractTextContent(content) {
    if (!content || !Array.isArray(content)) {
        return '';
    }
    
    let textContent = '';
    for (const contentBlock of content) {
        if (contentBlock.type === 'text' && contentBlock.text) {
            textContent += contentBlock.text + '\n';
        }
    }
    
    return textContent.trim();
}

/**
 * Extract tool details from the prior AI message that contains the tool_calls
 * This is needed because JSON tool messages don't include tool name and args
 */
function extractToolDetailsFromPriorMessage(toolCallId, stateMachine) {
    try {
        // Get the current output array from the state machine
        const currentOutput = stateMachine.currentOutput;
        if (!currentOutput || !Array.isArray(currentOutput)) {
            Logger.warn('No current output available for tool details extraction', { toolCallId });
            return null;
        }
        
        // Look for the AI message that contains this tool call
        for (let i = currentOutput.length - 1; i >= 0; i--) {
            const message = currentOutput[i];
            if (message.role === 'assistant' && message.tool_calls && Array.isArray(message.tool_calls)) {
                const toolCall = message.tool_calls.find(tc => tc.id === toolCallId);
                if (toolCall) {
                    return {
                        name: toolCall.name,
                        args: toolCall.args || {}
                    };
                }
            }
        }
        
        Logger.warn('Tool call details not found in prior messages', { toolCallId });
        return null;
    } catch (error) {
        Logger.error('Error extracting tool details from prior message', { error, toolCallId });
        return null;
    }
}

/**
 * Handle tool calls in assistant messages
 */
async function handleToolCalls(toolCalls, stateMachine, messageId) {
    Logger.info('Processing assistant message with tool calls', { 
        toolCallCount: toolCalls.length,
        messageId: messageId 
    });
    
    for (const toolCall of toolCalls) {
        Logger.info('Processing tool call', { 
            toolName: toolCall.name, 
            toolCallId: toolCall.id,
            args: toolCall.args 
        });
        
        if (stateMachine.updateToolCall) {
            try {
                stateMachine.updateToolCall(toolCall.id, {
                    name: toolCall.name,
                    args: toolCall.args,
                    status: 'pending'
                });
            } catch (error) {
                Logger.error('Error adding tool call to state machine', { error, toolCallId: toolCall.id });
            }
        }
    }
}

/**
 * Transform server interrupt format to state machine expected format
 */
function transformInterrupts(interrupts) {
    const transformedInterrupts = [];
    
    for (const interrupt of interrupts) {
        const toolCallId = interrupt.tool_call_id || 'unknown';
        const values = (interrupt.args && interrupt.args.value) || [];
        
        if (Array.isArray(values) && values.length > 0) {
            for (const v of values) {
                transformedInterrupts.push({
                    tool_call_id: toolCallId,
                    action_request: v.action_request || {},
                    config: v.config || {},
                    description: v.description || ''
                });
            }
        } else {
            // Fallback single interrupt mapping
            transformedInterrupts.push({
                tool_call_id: toolCallId,
                action_request: {},
                config: {},
                description: ''
            });
        }
    }
    
    return transformedInterrupts;
}
