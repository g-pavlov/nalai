/**
 * Response State Machine
 * Encapsulates event control and response state logic for agent flow design-agnostic UI
 * 
 * Key States:
 * 1. Progress - Shows workflow stage completion
 * 2. Tool Calling - Shows tool call streaming and execution
 * 3. Model Output - Shows progressive AI response rendering
 * 4. Interrupt - Shows human decision dialog
 * 5. Complete - Final state with no progress indicator
 */

import { Logger } from './logger.js';
import { createInterruptUI } from './interrupts.js';
import { getCurrentThreadId, setCurrentThreadId } from './state.js';
import { ErrorHandler } from './errorHandler.js';

// Human readable labels for node names (hardcoded mapping as specified)
const NODE_LABELS = {
    'call_model': 'AI Processing',
    'call_api': 'Tool Execution',
    'check_cache': 'Cache Check',
    'load_api_summaries': 'Loading API Summaries',
    'load_api_specs': 'Loading API Specifications',
    'select_relevant_apis': 'Selecting APIs'
};

// Response element structure
const RESPONSE_ELEMENTS = {
    PROGRESS: 'progress',
    CONTENT: 'content', 
    TOOLS: 'tools'
};

/**
 * Route SSE events to state machine
 * @param {Object} eventData - The parsed event data
 */
export async function routeEventToStateMachine(eventData) {
    const lastAssistantMessage = document.querySelector('.assistant-message:last-child');
    
    if (lastAssistantMessage && lastAssistantMessage.stateMachine && eventData.event) {
        lastAssistantMessage.stateMachine.handleEvent(eventData.event, eventData);
    } else {
        Logger.warn('No state machine found for SSE event processing', { 
            hasMessage: !!lastAssistantMessage,
            hasStateMachine: !!(lastAssistantMessage && lastAssistantMessage.stateMachine),
            hasEvent: !!eventData.event
        });
    }
}

export class ResponseStateMachine {
    constructor(assistantMessageDiv) {
        this.assistantMessageDiv = assistantMessageDiv;
        this.currentState = 'idle';
        this.elements = this.initializeElements();
        this.toolCalls = new Map(); // tool_call_id -> tool call data
        this.accumulatingToolCalls = new Map(); // tool_call_id -> accumulating data
        this.isComplete = false;
        this.accumulatedContent = ''; // For markdown parsing
        
        Logger.info('Response state machine initialized', { 
            messageId: assistantMessageDiv.dataset.messageId 
        });
        
        // Check initial content visibility and show fallback dots if needed
        this.updateContentVisibility();
    }

    /**
     * Initialize the predefined response element structure
     */
    initializeElements() {
        const elements = {};
        
        // Progress element - shows current workflow stage
        elements[RESPONSE_ELEMENTS.PROGRESS] = this.createProgressElement();
        
        // Content element - shows model output or interrupt dialog
        elements[RESPONSE_ELEMENTS.CONTENT] = this.createContentElement();
        
        // Tools element - shows tool calls and their results
        elements[RESPONSE_ELEMENTS.TOOLS] = this.createToolsElement();
        
        // Add elements to message
        Object.values(elements).forEach(element => {
            if (element) {
                this.assistantMessageDiv.appendChild(element);
            }
        });
        
        return elements;
    }

    /**
     * Create progress indicator element
     */
    createProgressElement() {
        const progress = document.createElement('div');
        progress.className = 'response-progress';
        progress.style.display = 'none'; // Hidden by default
        progress.innerHTML = `
            <div class="progress-header">
                <span class="progress-title">Starting...</span>
                <span class="progress-dots">...</span>
            </div>
        `;
        return progress;
    }

    /**
     * Create content element for model output or interrupt dialog
     */
    createContentElement() {
        const content = document.createElement('div');
        content.className = 'response-content';
        content.style.display = 'block'; // Visible by default
        return content;
    }

    /**
     * Create tools element for tool calls display
     */
    createToolsElement() {
        const tools = document.createElement('div');
        tools.className = 'response-tools';
        tools.style.display = 'none'; // Hidden by default
        return tools;
    }

    /**
     * Main event handler - routes events to appropriate state handlers
     */
    handleEvent(eventType, eventData) {
        Logger.info('🔄 STATE MACHINE EVENT', { 
            eventType, 
            currentState: this.currentState,
            messageId: this.assistantMessageDiv.dataset.messageId,
            eventData: JSON.stringify(eventData).substring(0, 200) + '...'
        });

        const previousState = this.currentState;

        switch (eventType) {
            case 'response.created':
                this.handleResponseCreated(eventData);
                break;
            case 'response.update':
                this.handleUpdateEvent(eventData);
                break;
            case 'response.output_tool_calls.delta':
                this.handleToolCallsDelta(eventData);
                break;
            case 'response.output_tool_calls.complete':
                this.handleToolCallsComplete(eventData);
                break;
            case 'response.output_text.delta':
                this.handleTextDelta(eventData);
                break;
            case 'response.interrupt':
                this.handleInterruptEvent(eventData);
                break;
            case 'response.tool':
                this.handleToolEvent(eventData);
                break;
            case 'response.completed':
                this.handleCompletedEvent(eventData);
                break;
            case 'response.error':
                this.handleErrorEvent(eventData);
                break;
            default:
                Logger.warn('❌ Unknown event type in state machine', { eventType });
        }

        // Log state transition if it changed
        if (previousState !== this.currentState) {
            Logger.info('🔄 STATE TRANSITION', {
                from: previousState,
                to: this.currentState,
                eventType: eventType,
                messageId: this.assistantMessageDiv.dataset.messageId
            });
        }
    }

    /**
     * Handle response.created events - extract conversation ID and initialize state
     */
    handleResponseCreated(eventData) {
        Logger.info('📝 RESPONSE CREATED EVENT', { 
            eventData: JSON.stringify(eventData).substring(0, 200) + '...',
            messageId: this.assistantMessageDiv.dataset.messageId
        });
        
        // Handle conversation ID from event data if present
        Logger.info('Checking conversation ID extraction', {
            hasConversation: !!eventData.conversation_id,
            conversationId: eventData.conversation_id,
            currentThreadId: getCurrentThreadId(),
            willUpdate: eventData.conversation_id && eventData.conversation_id !== getCurrentThreadId()
        });
        
        if (eventData.conversation_id && eventData.conversation_id !== getCurrentThreadId()) {
            // Validate that it's a proper domain-prefixed ID
            if (/^conv_[123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz]{10,}$/i.test(eventData.conversation_id)) {
                setCurrentThreadId(eventData.conversation_id);
                Logger.info('New conversation thread started from response.created event', { 
                    conversationId: eventData.conversation_id,
                    currentThreadIdAfterSet: getCurrentThreadId()
                });
            } else {
                Logger.warn('Invalid conversation ID format in response.created event', { conversationId: eventData.conversation_id });
            }
        } else if (eventData.conversation_id) {
            Logger.info('Conversation ID already set or same as current', {
                conversationId: eventData.conversation_id,
                currentThreadId: getCurrentThreadId()
            });
        } else {
            Logger.warn('No conversation ID found in response.created event');
        }
        
        // Initialize state for new response
        Logger.info('Initialized state for new response');
    }

    /**
     * Handle response.update events - workflow stage completion
     */
    handleUpdateEvent(eventData) {
        const task = eventData.task;
        const label = NODE_LABELS[task] || task;
        
        Logger.info('📋 UPDATE EVENT', { 
            task, 
            label,
            isFinalUpdate: this.isFinalUpdateBeforeCompletion(task),
            currentState: this.currentState
        });
        
        // Clear previous content unless this is the final update before completion
        if (!this.isFinalUpdateBeforeCompletion(task)) {
            Logger.info('🧹 Clearing content for intermediate update');
            this.clearContent();
        } else {
            Logger.info('💾 Preserving content for final update');
        }
        
        // Update progress element with current stage
        this.updateProgress(label);
        
        // Transition to progress state
        this.transitionToState('progress');
    }

    /**
     * Handle first response.output_tool_calls.delta event
     */
    handleToolCallsDelta(eventData) {
        Logger.info('🔧 TOOL CALLS DELTA', { 
            currentState: this.currentState,
            toolCallsCount: eventData.tool_calls?.length || 0,
            isFirstDelta: this.currentState !== 'tool_calling'
        });
        
        // On first delta event, transition to tool calling state
        if (this.currentState !== 'tool_calling') {
            Logger.info('🔄 Transitioning to tool calling state (first delta)');
            this.transitionToToolCallingState();
        } else {
            Logger.info('📝 Continuing tool calling state (subsequent delta)');
        }
        
        // Accumulate tool call data
        this.accumulateToolCalls(eventData);
    }

    /**
     * Handle response.output_tool_calls.complete event
     */
    handleToolCallsComplete(eventData) {
        Logger.info('✅ TOOL CALLS COMPLETE', { 
            currentState: this.currentState,
            completedToolCallsCount: eventData.tool_calls?.length || 0
        });
        
        // Store completed tool calls for later display
        this.storeCompletedToolCalls(eventData);
    }

    /**
     * Handle first response.output_text.delta event
     */
    handleTextDelta(eventData) {
        Logger.info('📝 TEXT DELTA', { 
            currentState: this.currentState,
            contentLength: eventData.content?.length || 0,
            contentPreview: eventData.content?.substring(0, 50) + '...',
            isFirstDelta: this.currentState !== 'model_output'
        });
        
        // On first delta event, transition to model output state
        if (this.currentState !== 'model_output') {
            Logger.info('🔄 Transitioning to model output state (first delta)');
            this.transitionToModelOutputState();
        } else {
            Logger.info('📝 Continuing model output state (subsequent delta)');
        }
        
        // Progressive content update
        this.updateContentProgressive(eventData.content);
    }

    /**
     * Handle response.interrupt event
     */
    handleInterruptEvent(eventData) {
        Logger.info('⚠️ INTERRUPT EVENT', { 
            currentState: this.currentState,
            interruptsCount: eventData.interrupts?.length || 0
        });
        
        // Ensure progress and tools elements take no space
        Logger.info('🙈 Hiding progress and tools elements');
        this.hideProgressAndTools();
        
        // Replace content with interrupt dialog
        Logger.info('💬 Showing interrupt dialog');
        this.showInterruptDialog(eventData);
        
        // Transition to interrupt state
        this.transitionToState('interrupt');
    }

    /**
     * Handle response.tool event - tool execution results
     */
    handleToolEvent(eventData) {
        Logger.info('🔧 TOOL EVENT', { 
            currentState: this.currentState,
            toolCallId: eventData.tool_call_id,
            toolName: eventData.tool_name,
            status: eventData.status,
            contentLength: eventData.content?.length || 0
        });
        
        const toolCallId = eventData.tool_call_id;
        const toolName = eventData.tool_name;
        let status = eventData.status;
        const content = eventData.content;
        const args = eventData.args || {};
        
        // Check if this tool call was part of an interrupt flow
        const existingToolCall = this.toolCalls.get(toolCallId);
        if (existingToolCall && existingToolCall.source === 'interrupt') {
            // For interrupt-originated tool calls, only override with 'rejected' if that was the user decision
            if (existingToolCall.status === 'rejected') {
                status = 'rejected';
                Logger.info('🔧 Using tracked interrupt rejected status', { 
                    toolCallId, 
                    trackedStatus: status,
                    source: existingToolCall.source
                });
            }
            // For all other cases (pending, confirmed), let the API status flow through
        } 

        
        // Update tool call with execution results
        // Preserve original tool call data (name) and only update execution-specific fields
        this.updateToolCall(toolCallId, {
            status: status,
            content: content,
            timestamp: new Date().toISOString(),
            args: args, // args may have changed due to interrupt decisions
            source: 'response.tool' // Track the source of this status update
        });
        
        // Update tools display
        Logger.info('🔄 Updating tools display');
        this.updateToolsDisplay();
    }

    /**
     * Handle interrupt resume decision and update tool call status
     * @param {string} toolCallId - The tool call ID being resumed
     * @param {string} decision - The user's decision: 'accept', 'ignore', 'edit', 'respond'
     * @param {any} args - Additional arguments for the decision
     */
    handleInterruptResume(toolCallId, decision, args = null) {
        Logger.info('🔄 INTERRUPT RESUME DECISION', {
            toolCallId,
            decision,
            hasArgs: !!args,
            messageId: this.assistantMessageDiv.dataset.messageId
        });

        let status = null;
        
        // Map interrupt decision to tool call status
        // Only set explicit status for decisions that don't result in tool execution
        switch (decision) {
            case 'accept':
                // Let the API determine the final status when tool executes
                break;
            case 'ignore':
                status = 'rejected'; // User explicitly rejected, override API
                break;
            case 'edit':
                // Let the API determine the final status when tool executes
                break;
            case 'respond':
                // Let the API determine the final status when tool executes
                break;
            default:
                Logger.warn('Unknown interrupt decision', { decision, toolCallId });
        }

        // Get the existing tool call to preserve its data
        const existingToolCall = this.toolCalls.get(toolCallId);
        if (!existingToolCall) {
            Logger.warn('Tool call not found for interrupt resume', { toolCallId, decision });
            return;
        }

        // Update tool call status while preserving all existing data
        const updateData = {
            status: status || existingToolCall.status, // Preserve existing status if not explicitly set
            confirmed: decision === 'accept' || decision === 'ignore' ? decision === 'accept' : undefined,
            source: 'interrupt',
            timestamp: new Date().toISOString()
        };
        
        // Ensure we preserve the name and args from the original tool call
        if (existingToolCall.name) {
            updateData.name = existingToolCall.name;
        }
        if (existingToolCall.args) {
            updateData.args = existingToolCall.args;
        }
        
        this.updateToolCall(toolCallId, updateData);

        // Update tools display
        Logger.info('🔄 Updating tools display after interrupt resume', {
            toolCallId,
            decision,
            preservedName: updateData.name,
            preservedArgs: !!updateData.args
        });
        this.updateToolsDisplay();
    }

    /**
     * Handle response.completed event
     */
    handleCompletedEvent(eventData) {
        Logger.info('🎉 COMPLETED EVENT', { 
            currentState: this.currentState,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
        
        this.isComplete = true;
        
        // Progress element takes no space
        Logger.info('🙈 Hiding progress element');
        this.hideProgress();
        
        // Transition to complete state
        this.transitionToState('complete');
    }

    /**
     * Handle response.error event
     */
    handleErrorEvent(eventData) {
        Logger.error('❌ ERROR EVENT', { 
            currentState: this.currentState,
            error: eventData.error,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
        
        this.isComplete = true;
        
        // Hide progress and tools
        this.hideProgress();
        this.hideProgressAndTools();
        
        // Use ErrorHandler to show user-friendly error message
        const errorMessage = eventData.error || 'An error occurred while processing your request';
        ErrorHandler.showUserError(errorMessage, 'API Response');
        
        // Show error message in content as well
        this.showErrorContent(errorMessage);
        
        // Transition to error state
        this.transitionToState('error');
    }

    /**
     * Transition to tool calling state
     */
    transitionToToolCallingState() {
        Logger.info('🔄 TRANSITION: Tool Calling State', {
            from: this.currentState,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
        
        // Replace progress with tool calling title
        this.updateProgress('Tool Calling');
        
        // Clear previous content
        this.clearContent();
        
        this.currentState = 'tool_calling';
    }

    /**
     * Transition to model output state
     */
    transitionToModelOutputState() {
        Logger.info('🔄 TRANSITION: Model Output State', {
            from: this.currentState,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
        
        // Replace progress with AI response title
        this.updateProgress('AI Response');
        
        // Clear previous content
        this.clearContent();
        
        this.currentState = 'model_output';
    }

    /**
     * Transition to specified state
     */
    transitionToState(newState) {
        Logger.info('🔄 TRANSITION: Generic State', { 
            from: this.currentState, 
            to: newState,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
        
        this.currentState = newState;
    }

    /**
     * Update progress element with label
     */
    updateProgress(label) {
        const progress = this.elements[RESPONSE_ELEMENTS.PROGRESS];
        const title = progress.querySelector('.progress-title');
        if (title) {
            title.textContent = label;
        }
        
        // Show progress element
        progress.style.display = 'block';
        
        Logger.info('📊 Progress Updated and Shown', {
            label: label,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
    }

    /**
     * Hide progress element (takes no space)
     */
    hideProgress() {
        const progress = this.elements[RESPONSE_ELEMENTS.PROGRESS];
        progress.style.display = 'none';
        
        Logger.info('🙈 Progress Hidden', {
            messageId: this.assistantMessageDiv.dataset.messageId
        });
    }

    /**
     * Hide progress and tools elements (takes no space)
     */
    hideProgressAndTools() {
        this.hideProgress();
        const tools = this.elements[RESPONSE_ELEMENTS.TOOLS];
        tools.style.display = 'none';
        
        Logger.info('🙈 Progress and Tools Hidden', {
            messageId: this.assistantMessageDiv.dataset.messageId
        });
    }

    /**
     * Clear content element
     */
    clearContent() {
        const content = this.elements[RESPONSE_ELEMENTS.CONTENT];
        content.innerHTML = '';
        this.accumulatedContent = ''; // Reset accumulated content
        
        // Hide content element when no content
        this.updateContentVisibility();
        
        Logger.info('🧹 Content Cleared and Hidden', {
            messageId: this.assistantMessageDiv.dataset.messageId
        });
    }

    /**
     * Update content visibility based on whether there's content to show
     */
    updateContentVisibility() {
        const content = this.elements[RESPONSE_ELEMENTS.CONTENT];
        const hasContent = this.accumulatedContent && this.accumulatedContent.trim().length > 0;
        
        // Check if progress indicator is visible
        const progress = this.elements[RESPONSE_ELEMENTS.PROGRESS];
        const hasProgress = progress && progress.style.display !== 'none';
        
        // Check if interrupt dialog is present
        const hasInterrupt = this.assistantMessageDiv.querySelector('.interrupt-container');
        
        if (hasContent) {
            content.style.display = 'block';
            // Remove fallback dots if they exist
            this.removeFallbackDots();
        } else {
            // No content - check if we should show fallback dots
            if (!hasProgress && !hasInterrupt) {
                // No content AND no progress AND no interrupt - show fallback dots
                this.showFallbackDots();
                content.style.display = 'block'; // Show content element to display dots
            } else {
                // No content but progress or interrupt is visible - hide content
                content.style.display = 'none';
                this.removeFallbackDots();
            }
        }
        
        Logger.info('👁️ Content visibility updated', {
            hasContent: hasContent,
            hasProgress: hasProgress,
            hasInterrupt: hasInterrupt,
            contentLength: this.accumulatedContent ? this.accumulatedContent.length : 0,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
    }

    /**
     * Show fallback dots when no content and no progress
     */
    showFallbackDots() {
        const content = this.elements[RESPONSE_ELEMENTS.CONTENT];
        
        // Only add dots if they don't already exist
        if (!content.querySelector('.progress-dots')) {
            const dotsElement = document.createElement('span');
            dotsElement.className = 'progress-dots';
            dotsElement.textContent = '...';
            
            content.appendChild(dotsElement);
            Logger.info('🔵 Added fallback dots indicator', {
                messageId: this.assistantMessageDiv.dataset.messageId
            });
        }
    }

    /**
     * Remove fallback dots
     */
    removeFallbackDots() {
        const content = this.elements[RESPONSE_ELEMENTS.CONTENT];
        const existingDots = content.querySelector('.progress-dots');
        
        if (existingDots) {
            existingDots.remove();
            Logger.info('🔵 Removed fallback dots indicator', {
                messageId: this.assistantMessageDiv.dataset.messageId
            });
        }
    }

    /**
     * Update content progressively
     */
    updateContentProgressive(newContent) {
        const content = this.elements[RESPONSE_ELEMENTS.CONTENT];
        
        // Accumulate content for markdown parsing
        if (this.accumulatedContent) {
            this.accumulatedContent += newContent;
        } else {
            this.accumulatedContent = newContent;
        }
        
        // Parse markdown and update content if we have content
        if (this.accumulatedContent && this.accumulatedContent.trim().length > 0) {
            try {
                content.innerHTML = marked.parse(this.accumulatedContent);
            } catch (error) {
                Logger.error('Markdown parsing error', { error, content: this.accumulatedContent });
                content.textContent = this.accumulatedContent; // Fallback to plain text
            }
        }
        
        // Update content visibility
        this.updateContentVisibility();
        
        Logger.info('📝 Content Updated Progressively with Markdown', {
            newContentLength: newContent.length,
            totalContentLength: this.accumulatedContent.length,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
    }

    /**
     * Show error content in content element
     */
    showErrorContent(errorMessage) {
        const content = this.elements[RESPONSE_ELEMENTS.CONTENT];
        
        // Clear any existing content
        content.innerHTML = '';
        
        // Simple error text display - no HTML recreation
        content.textContent = `Error: ${errorMessage}`;
        content.className = 'response-content error-content';
        
        // Update content visibility
        this.updateContentVisibility();
        
        Logger.info('❌ Error content displayed', {
            errorMessage: errorMessage,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
    }

    /**
     * Show interrupt dialog in content element
     */
    showInterruptDialog(eventData) {
        const content = this.elements[RESPONSE_ELEMENTS.CONTENT];
        
        // Extract interrupt information from SSE format
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
        
        // Try to get tool call ID from interrupt event first, then from stored tool calls
        let toolCallId = interrupt.tool_call_id;
        if (!toolCallId || toolCallId === 'unknown') {
            // Find the tool call ID from stored tool calls that matches the action
            for (const [storedToolCallId, toolCall] of this.toolCalls.entries()) {
                if (toolCall.name === action) {
                    toolCallId = storedToolCallId;
                    Logger.info('Found tool call ID from stored tool calls', {
                        action: action,
                        toolCallId: toolCallId
                    });
                    break;
                }
            }
        }
        
        // If still no tool call ID, use the first stored tool call ID
        if (!toolCallId || toolCallId === 'unknown') {
            const firstToolCallId = this.toolCalls.keys().next().value;
            if (firstToolCallId) {
                toolCallId = firstToolCallId;
                Logger.info('Using first stored tool call ID as fallback', {
                    toolCallId: toolCallId
                });
            }
        }
        
        if (!action) {
            Logger.error('Missing action in SSE interrupt event', { eventData });
            return;
        }
        
        // Create interrupt UI using existing interrupt module
        const actionRequestObj = { action, args };
        const interruptInfoWithConfig = {
            config: config,
            description: description
        };
        
        createInterruptUI(this.assistantMessageDiv, actionRequestObj, interruptInfoWithConfig);
        
        // Store the complete interrupt data for later use (same as streaming module)
        window.currentInterrupt = {
            value: {
                tool_call_id: toolCallId,
                action_request: actionRequest,
                config: config,
                description: description,
                conversation_id: getCurrentThreadId() // Store conversation ID for resume requests
            },
            resumable: true, // SSE interrupts are always resumable
            ns: 'interrupt'
        };
        
        // Show content element
        content.style.display = 'block';
        
        // Update content visibility to remove fallback dots now that interrupt dialog is shown
        this.updateContentVisibility();
        
        Logger.info('💬 Interrupt dialog shown in content', {
            messageId: this.assistantMessageDiv.dataset.messageId,
            toolCallId: toolCallId,
            action: action,
            storedToolCallsCount: this.toolCalls.size
        });
    }

    /**
     * Accumulate tool calls from delta events
     */
    accumulateToolCalls(eventData) {
        if (eventData.tool_calls && Array.isArray(eventData.tool_calls)) {
            Logger.info('📦 Accumulating tool calls', {
                toolCallsCount: eventData.tool_calls.length,
                currentAccumulatingCount: this.accumulatingToolCalls.size
            });
            
            eventData.tool_calls.forEach(toolCallDelta => {
                const toolCallId = toolCallDelta.id;
                
                if (!toolCallId) return;
                
                // Get or create accumulating tool call
                if (!this.accumulatingToolCalls.has(toolCallId)) {
                    this.accumulatingToolCalls.set(toolCallId, {
                        id: toolCallId,
                        name: '',
                        arguments: '',
                        function_call: {}
                    });
                    Logger.info('🆕 Created new accumulating tool call', { toolCallId });
                }
                
                const accumulating = this.accumulatingToolCalls.get(toolCallId);
                
                // Accumulate data
                if (toolCallDelta.name) {
                    accumulating.name = toolCallDelta.name;
                }
                
                if (toolCallDelta.function_call) {
                    if (toolCallDelta.function_call.name) {
                        accumulating.function_call.name = toolCallDelta.function_call.name;
                    }
                    if (toolCallDelta.function_call.arguments) {
                        accumulating.function_call.arguments = 
                            (accumulating.function_call.arguments || '') + toolCallDelta.function_call.arguments;
                    }
                }
                
                // Update name from function_call if available
                if (accumulating.function_call.name) {
                    accumulating.name = accumulating.function_call.name;
                }
                
                Logger.info('📝 Updated accumulating tool call', {
                    toolCallId,
                    name: accumulating.name,
                    argumentsLength: accumulating.function_call.arguments?.length || 0
                });
            });
        }
    }

    /**
     * Store completed tool calls
     */
    storeCompletedToolCalls(eventData) {
        if (eventData.tool_calls && Array.isArray(eventData.tool_calls)) {
            Logger.info('💾 Storing completed tool calls', {
                completedCount: eventData.tool_calls.length,
                currentStoredCount: this.toolCalls.size
            });
            
            eventData.tool_calls.forEach(toolCall => {
                const toolCallId = toolCall.id;
                const toolName = toolCall.name;
                const args = toolCall.args || {};
                
                if (!toolCallId || !toolName) return;
                
                this.toolCalls.set(toolCallId, {
                    id: toolCallId,
                    name: toolName,
                    args: args,
                    status: 'pending',
                    content: null,
                    timestamp: new Date().toISOString(),
                    source: 'output_tool_calls_complete' // Track the source
                });
                
                Logger.info('💾 Stored completed tool call', {
                    toolCallId,
                    name: toolName,
                    args: args,
                    source: 'output_tool_calls_complete'
                });
            });
        }
    }

    /**
     * Update tool call with execution results
     */
    updateToolCall(toolCallId, data) {
        const existing = this.toolCalls.get(toolCallId);
        if (existing) {
            // Merge new data with existing data, preserving existing fields
            Object.assign(existing, data);
            Logger.info('🔄 Updated existing tool call', {
                toolCallId,
                name: data.name || existing.name,
                status: data.status || existing.status,
                source: data.source || existing.source
            });
        } else {
            // Create new tool call with required fields
            const newToolCall = {
                id: toolCallId,
                name: data.name || 'Unknown tool',
                status: data.status || 'pending',
                content: data.content || null,
                args: data.args || {},
                timestamp: data.timestamp || new Date().toISOString(),
                source: data.source || 'unknown'
            };
            this.toolCalls.set(toolCallId, newToolCall);
            Logger.info('🆕 Created new tool call', {
                toolCallId,
                name: newToolCall.name,
                status: newToolCall.status,
                source: newToolCall.source
            });
        }
    }

    /**
     * Update tools display
     */
    updateToolsDisplay() {
        const tools = this.elements[RESPONSE_ELEMENTS.TOOLS];
        
        if (this.toolCalls.size === 0) {
            tools.style.display = 'none';
            Logger.info('🙈 Tools display hidden (no tool calls)');
            return;
        }
        
        // Create tools indicator button with unique ID
        const toolCallsArray = Array.from(this.toolCalls.values());
        const toolsPanelId = `tools-panel-${this.assistantMessageDiv.dataset.messageId}`;
        const toolsHTML = `
            <div class="message-tools-indicator" data-tools-panel="${toolsPanelId}">
                Tools called (${this.toolCalls.size})
            </div>
            <div class="tools-panel" id="${toolsPanelId}">
                ${toolCallsArray.map(toolCall => `
                    <div class="tool-call-item">
                        <div class="tool-call-header">
                            <div class="tool-call-name">${toolCall.name}</div>
                            <div class="tool-call-status-badge ${toolCall.status}">
                                <span class="status-text">${this.getStatusText(toolCall.status)}</span>
                            </div>
                        </div>
                        <div class="tool-call-section">
                            <div class="tool-call-section-title">Arguments</div>
                            <div class="tool-call-args">${this.formatToolArgs(toolCall.args)}</div>
                        </div>
                        ${toolCall.content ? `
                            <div class="tool-call-section">
                                <div class="tool-call-section-title">Result</div>
                                <div class="tool-call-response">${this.formatToolResponse(toolCall.content)}</div>
                            </div>
                        ` : ''}
                    </div>
                `).join('')}
            </div>
        `;
        
        tools.innerHTML = toolsHTML;
        tools.style.display = 'block';
        
        // Add click event handler for tools indicator
        const toolsIndicator = tools.querySelector('.message-tools-indicator');
        if (toolsIndicator) {
            toolsIndicator.addEventListener('click', () => {
                const toolsPanel = tools.querySelector('.tools-panel');
                if (toolsPanel) {
                    toolsPanel.classList.toggle('expanded');
                    Logger.info('🔄 Tools panel toggled', {
                        expanded: toolsPanel.classList.contains('expanded'),
                        messageId: this.assistantMessageDiv.dataset.messageId
                    });
                }
            });
        }
        
        Logger.info('🔄 Tools display updated with collapsible panel', {
            toolCallsCount: this.toolCalls.size,
            messageId: this.assistantMessageDiv.dataset.messageId
        });
    }

    /**
     * Format tool arguments for display
     */
    formatToolArgs(args) {
        if (!args || Object.keys(args).length === 0) {
            return '<em>No arguments</em>';
        }
        
        try {
            return JSON.stringify(args, null, 2);
        } catch (error) {
            return String(args);
        }
    }

    /**
     * Format tool response for display
     */
    formatToolResponse(content) {
        if (!content) {
            return '<em>No response</em>';
        }
        
        try {
            // Try to parse as JSON for pretty formatting
            const parsed = JSON.parse(content);
            return JSON.stringify(parsed, null, 2);
        } catch (error) {
            // Return as plain text
            return String(content);
        }
    }

    /**
     * Get human-readable status text for tool call status
     */
    getStatusText(status) {
        switch (status) {
            case 'confirmed':
                return 'Confirmed';
            case 'completed':
            case 'success':
                return 'Completed';
            case 'pending':
                return 'Pending';
            case 'error':
                return 'Error';
            case 'rejected':
                return 'Rejected';
            case 'ready':
                return 'Ready';
            default:
                return status.charAt(0).toUpperCase() + status.slice(1);
        }
    }

    /**
     * Check if this is the final update before completion
     */
    isFinalUpdateBeforeCompletion(task) {
        // This would need to be determined based on the specific flow
        // For now, assume call_model is the final task
        return task === 'call_model';
    }

    /**
     * Get current state
     */
    getCurrentState() {
        return this.currentState;
    }

    /**
     * Get tool calls
     */
    getToolCalls() {
        return Array.from(this.toolCalls.values());
    }

    /**
     * Cleanup state machine
     */
    cleanup() {
        Logger.info('Cleaning up response state machine');
        this.currentState = 'idle';
        this.toolCalls.clear();
        this.accumulatingToolCalls.clear();
        this.isComplete = false;
    }
}
