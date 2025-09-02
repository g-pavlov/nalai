/**
 * Interrupts Module
 * Handles human review scenarios and interrupt processing
 */

import { DOM } from './dom.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { NetworkManager } from './network.js';
import { buildApiUrl, API_CONFIG } from './config.js';
import { getCurrentThreadId } from './state.js';

import { cleanupMessageProcessing } from './messages.js';
import { parseSSEStream } from './api_responses_sse.js';
import { routeEventToStateMachine } from './responses.js';
import { processCompleteResponseWithStateMachine } from './api_responses_json.js';

export async function handleInterrupt(responseType, args = null) {
    if (!window.currentInterrupt) {
        Logger.error('No current interrupt to handle');
        ErrorHandler.showUserError('No interrupt to handle');
        return;
    }
    
    Logger.info('Handling interrupt', { responseType, args });

    // Handle edit case - show edit UI instead of sending request
    if (responseType === 'edit' && !args) {
        showEditInterruptUI();
        return;
    }
    
    // Disable all action buttons and show progress (only for non-edit cases)
    disableInterruptActions();
    
    // Update tool call status in state machine
    updateToolCallStatusInStateMachine(responseType, args);
    
    // Capture edited tool call arguments if this is an edit submission
    captureEditedToolCallArguments(responseType, args);
    
    try {
        // Validate conversation context
        validateConversationContext();
        
        // Create tool decision payload
        const toolDecision = createToolDecisionPayload(responseType, args);
        
        // Send resume request
        await sendResumeRequest(toolDecision, responseType, args);
        
    } catch (error) {
        Logger.error('Interrupt handling caught error', { 
            error, 
            errorType: typeof error, 
            errorMessage: error?.message,
            errorStack: error?.stack 
        });
        ErrorHandler.handleError(error, 'Interrupt handling');
        
        // Re-enable buttons on error
        enableInterruptActions();
    }
}

/**
 * Update tool call status in state machine based on user decision
 */
function updateToolCallStatusInStateMachine(responseType, args) {
    const toolCallId = window.currentInterrupt.value.tool_call_id;
    if (!toolCallId || toolCallId === 'unknown') {
        return;
    }
    
    // Find the state machine for this message
    const assistantMessage = document.querySelector('.assistant-message:last-child');
    if (!assistantMessage?.stateMachine) {
        Logger.warn('No state machine found for interrupt resume status update');
        return;
    }
    
    // Map responseType to decision for state machine
    let decision = responseType;
    if (responseType === 'reject') {
        decision = 'ignore'; // Map reject to ignore for consistency
    }
    
    // Update tool call status in state machine
    assistantMessage.stateMachine.handleInterruptResume(toolCallId, decision, args);
    Logger.info('Updated tool call status in state machine', {
        toolCallId,
        decision,
        hasArgs: !!args
    });
}

/**
 * Capture edited tool call arguments if this is an edit submission
 */
function captureEditedToolCallArguments(responseType, args) {
    if (responseType === 'edit' && args && window.currentInterrupt?.value?.action_request?.action) {
        const actionRequest = window.currentInterrupt.value.action_request;
        const toolCallId = window.currentInterrupt.value.tool_call_id;
        
        Logger.info('Capturing edited tool call arguments', { 
            toolName: actionRequest.action, 
            toolCallId: toolCallId,
            originalArgs: actionRequest.args, 
            editedArgs: args 
        });
    }
}

/**
 * Validate conversation context before proceeding
 */
function validateConversationContext() {
    Logger.info('Current thread ID format', { currentThreadId: getCurrentThreadId() });
    Logger.info('Current interrupt structure', { 
        currentInterrupt: window.currentInterrupt,
        interruptValue: window.currentInterrupt?.value,
        actionRequest: window.currentInterrupt?.value?.action_request
    });
    
    const currentThreadId = getCurrentThreadId();
    Logger.info('Checking conversation ID for resume request', {
        currentThreadId: currentThreadId,
        hasThreadId: !!currentThreadId,
        threadIdType: typeof currentThreadId
    });
    
    if (!currentThreadId) {
        throw new Error('No conversation ID available for resume request');
    }
}

/**
 * Create tool decision payload based on response type
 */
function createToolDecisionPayload(responseType, args) {
    const toolCallId = window.currentInterrupt.value.tool_call_id || 'unknown';
    
    switch (responseType) {
        case 'edit':
            return {
                type: 'tool_decision',
                tool_call_id: toolCallId,
                decision: 'edit',
                args: args
            };
        case 'accept':
            return {
                type: 'tool_decision',
                tool_call_id: toolCallId,
                decision: 'accept'
            };
        case 'reject':
            return {
                type: 'tool_decision',
                tool_call_id: toolCallId,
                decision: 'reject',
                message: args || 'User rejected the tool call'
            };
        default:
            return {
                type: 'tool_decision',
                tool_call_id: toolCallId,
                decision: 'feedback',
                message: args || 'User feedback'
            };
    }
}

/**
 * Send resume request to the API
 */
async function sendResumeRequest(toolDecision, responseType, args) {
    // Get current streaming preference from settings
    const isStreamingEnabled = DOM.streamingToggle.checked;
    
    const resumePayload = {
        conversation_id: getCurrentThreadId(),
        input: [toolDecision],
        stream: isStreamingEnabled ? 'full' : 'off'
    };

    Logger.info('Sending resume payload', { resumePayload });

    // Log the full request details for debugging
    Logger.info('Resume request details', {
        url: buildApiUrl(API_CONFIG.URL_TEMPLATES.MESSAGES),
        method: 'POST',
        payload: resumePayload,
        responseType,
        args
    });

    const requestUrl = buildApiUrl(API_CONFIG.URL_TEMPLATES.MESSAGES);
    const requestOptions = createResumeRequestOptions(resumePayload, isStreamingEnabled);
    
    Logger.info('About to send resume request', { 
        url: requestUrl, 
        options: requestOptions,
        headers: requestOptions.headers 
    });
    
    const response = await NetworkManager.fetchWithRetry(requestUrl, requestOptions);

    if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`);
    }

    if (isStreamingEnabled) {
        await handleResumeStream(response);
    } else {
        await handleResumeNonStreaming(response);
    }
}

/**
 * Create request options for resume request
 */
function createResumeRequestOptions(resumePayload, isStreamingEnabled) {
    // Set Accept header based on streaming preference
    const acceptHeader = isStreamingEnabled ? 'text/event-stream' : 'application/json';
    
    return {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'Accept': acceptHeader,
            'Authorization': 'Bearer dev-token'
        },
        body: JSON.stringify(resumePayload)
    };
}

async function handleResumeStream(response) {
    Logger.info('Starting resume stream processing', { responseStatus: response.status });

    // Parse SSE stream and route events to state machine
    await parseSSEStream(
        response,
        routeEventToStateMachine,
        handleResumeStreamComplete,
        handleResumeStreamError
    );
}

async function handleResumeNonStreaming(response) {
    Logger.info('Starting resume non-streaming processing', { responseStatus: response.status });
    
    // Find the existing assistant message element that contains the interrupt dialog
    const existingAssistantMessage = document.querySelector('.assistant-message:last-child');
    if (!existingAssistantMessage) {
        Logger.error('No existing assistant message found for resume');
        return;
    }
    
    Logger.info('Reusing existing assistant message for resume', { 
        messageId: existingAssistantMessage.dataset.messageId 
    });
    
    // Clear the interrupt dialog content to make room for the resume response
    const contentElement = existingAssistantMessage.querySelector('.response-content');
    if (contentElement) {
        contentElement.innerHTML = '';
        Logger.info('Cleared interrupt dialog content for resume response');
    }
    
    // Process the non-streaming response using the existing message element
    await processCompleteResponseWithStateMachine(response, existingAssistantMessage);
    
    // Handle completion
    handleResumeStreamComplete();
}

function handleResumeStreamComplete() {
    Logger.info('Resume stream completed successfully');
    
    // Cleanup interrupt UI and state
    cleanupInterruptState();
    
    // Clear processing state
    cleanupMessageProcessing();
}

function handleResumeStreamError(error) {
    Logger.error('Resume stream error', { error });
    
    // Clear interrupt state on error
    cleanupInterruptState();
    
    // Clear processing state
    cleanupMessageProcessing();
}

function cleanupInterruptState() {
    // Remove interrupt UI
    const existingInterrupt = document.querySelector('.interrupt-container');
    if (existingInterrupt) {
        existingInterrupt.remove();
        Logger.info('Interrupt container removed');
    }
    
    // Clear interrupt state
    if (window.currentInterrupt) {
        window.currentInterrupt = null;
        Logger.info('Interrupt state cleared');
    }
}

function disableInterruptActions() {
    const interruptContainer = document.querySelector('.interrupt-container');
    if (!interruptContainer) {
        Logger.warn('No interrupt container found');
        return;
    }
    
    // Remove the interrupt UI to make room for streaming content
    interruptContainer.remove();
    Logger.info('Removed interrupt UI to make room for streaming content');
}

function enableInterruptActions() {
    // This function is no longer needed since we remove the interrupt UI
    // instead of just disabling buttons
    Logger.info('enableInterruptActions called but interrupt UI is already removed');
}

export function createInterruptUI(assistantMessageDiv, actionRequest, interruptInfo) {
    // Remove any existing interrupt UI first
    const existingInterrupt = document.querySelector('.interrupt-container');
    if (existingInterrupt) {
        existingInterrupt.remove();
        Logger.info('Removed existing interrupt UI before creating new one');
    }
    
    // Content visibility is now managed by the state machine
    Logger.info('Content visibility managed by state machine for interrupt UI');
    

    
    const interruptDiv = document.createElement('div');
    interruptDiv.className = 'interrupt-container fade-in';
    
    // Extract configuration from interrupt info
    const config = interruptInfo?.config || {};
    const allowAccept = config.allow_accept !== false; // Default to true if not specified
    const allowEdit = config.allow_edit === true;
    const allowRespond = config.allow_respond === true;
    
    Logger.info('Creating interrupt UI with config', { 
        allowAccept, 
        allowEdit, 
        allowRespond, 
        config 
    });
    
    // Build action buttons based on configuration
    let actionButtons = '';
    
    if (allowAccept) {
        actionButtons += `
            <button class="interrupt-button accept" onclick="handleInterrupt('accept')" title="Accept and execute this tool call">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20,6 9,17 4,12"></polyline>
                </svg>
                Accept
            </button>`;
    }
    
    if (allowEdit) {
        actionButtons += `
            <button class="interrupt-button edit" onclick="handleInterrupt('edit')" title="Edit the tool arguments before execution">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                Edit
            </button>`;
    }
    
    if (allowRespond) {
        actionButtons += `
            <button class="interrupt-button reject" onclick="handleInterrupt('reject')" title="Reject this tool call">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
                Reject
            </button>`;
    }
    
    // If no actions are allowed, show a message
    if (!actionButtons) {
        actionButtons = '<div class="interrupt-no-actions">No actions available for this interrupt</div>';
    }
    
    interruptDiv.innerHTML = `
        <div class="interrupt-header">
            <div class="interrupt-title">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <circle cx="12" cy="12" r="10"></circle>
                    <line x1="12" y1="8" x2="12" y2="12"></line>
                    <line x1="12" y1="16" x2="12.01" y2="16"></line>
                </svg>
                Human Review Required
            </div>
            ${interruptInfo?.description ? `
                <div class="interrupt-description">
                    ${interruptInfo.description}
                </div>
            ` : ''}
        </div>
        <div class="interrupt-details">
            <div class="tool-info">
                <strong>Tool:</strong> ${actionRequest.action || 'Unknown'}
            </div>
            <div class="args-section">
                <strong>Arguments:</strong>
                <pre class="args-display">${JSON.stringify(actionRequest.args || {}, null, 2)}</pre>
            </div>
        </div>
        <div class="interrupt-actions">
            ${actionButtons}
        </div>
    `;
    
    // Insert the interrupt container BEFORE the streaming progress container
    // This ensures the call_model response appears below the interrupt dialog
    // Insert the interrupt UI into the message
    assistantMessageDiv.appendChild(interruptDiv);
    
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

export function showEditInterruptUI() {
    if (!window.currentInterrupt) {
        Logger.error('No current interrupt to edit');
        return;
    }

    const actionRequest = window.currentInterrupt.value?.action_request;
    if (!actionRequest) {
        Logger.error('No action request found in interrupt');
        return;
    }

    // Find the existing interrupt container
    const interruptContainer = document.querySelector('.interrupt-container');
    if (!interruptContainer) {
        Logger.error('No interrupt container found');
        return;
    }

    // Replace the interrupt UI with edit UI
    interruptContainer.innerHTML = `
        <div class="interrupt-header">
            <div class="interrupt-title">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
                    <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
                </svg>
                Edit Tool Arguments
            </div>
            ${window.currentInterrupt.value?.description ? `
                <div class="interrupt-description">
                    ${window.currentInterrupt.value.description}
                </div>
            ` : ''}
        </div>
        <div class="interrupt-details">
            <div class="tool-info">
                <strong>Tool:</strong> ${actionRequest.action || 'Unknown'}
            </div>
            <div class="args-section">
                <strong>Edit Arguments:</strong>
                <div 
                    id="editArgsTextarea" 
                    class="edit-args-textarea"
                    contenteditable="true"
                >${JSON.stringify(actionRequest.args || {}, null, 2)}</div>
                <div class="edit-validation" id="editValidation"></div>
            </div>
        </div>
        <div class="interrupt-actions">
            <button class="interrupt-button cancel" onclick="cancelEditInterrupt()" title="Cancel editing and return to original interrupt">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <line x1="18" y1="6" x2="6" y2="18"></line>
                    <line x1="6" y1="6" x2="18" y2="18"></line>
                </svg>
                Cancel
            </button>
            <button class="interrupt-button submit" onclick="submitEditedInterrupt()" title="Submit the edited arguments">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="20,6 9,17 4,12"></polyline>
                </svg>
                Submit
            </button>
        </div>
    `;

    // Focus on the contenteditable div
    const textarea = document.getElementById('editArgsTextarea');
    if (textarea) {
        textarea.focus();
        // For contenteditable divs, we need to select all content differently
        const range = document.createRange();
        range.selectNodeContents(textarea);
        const selection = window.getSelection();
        selection.removeAllRanges();
        selection.addRange(range);
    }
}

export function cancelEditInterrupt() {
    if (!window.currentInterrupt) return;

    // Recreate the original interrupt UI
    const interruptContainer = document.querySelector('.interrupt-container');
    if (interruptContainer) {
        const actionRequest = window.currentInterrupt.value?.action_request;
        const interruptInfo = window.currentInterrupt.value;
        
        // Find the assistant message div that contains this interrupt
        const assistantMessageDiv = interruptContainer.closest('.assistant-message');
        if (assistantMessageDiv) {
            // Remove the current interrupt container
            interruptContainer.remove();
            // Recreate the original interrupt UI
            createInterruptUI(assistantMessageDiv, actionRequest, interruptInfo);
        }
    }
}

export function submitEditedInterrupt() {
    if (!window.currentInterrupt) {
        Logger.error('No current interrupt to submit');
        return;
    }

    const textarea = document.getElementById('editArgsTextarea');
    const validationDiv = document.getElementById('editValidation');
    
    if (!textarea) {
        Logger.error('Edit textarea not found');
        return;
    }

    try {
        // Parse the edited JSON - use textContent for contenteditable div
        const editedArgs = JSON.parse(textarea.textContent.trim());
        
        // Clear any previous validation errors
        validationDiv.innerHTML = '';
        validationDiv.className = 'edit-validation';
        
        Logger.info('Submitting edited interrupt', { editedArgs });
        
        // Submit the edited interrupt
        handleInterrupt('edit', editedArgs);
        
    } catch (error) {
        // Show validation error
        validationDiv.innerHTML = `<div class="validation-error">❌ Invalid JSON: ${error.message}</div>`;
        validationDiv.className = 'edit-validation has-error';
        Logger.warn('Invalid JSON in edit form', { error: error.message });
    }
}
