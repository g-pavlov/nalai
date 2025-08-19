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
import { processStreamEvent, resetStreamingStateAfterInterrupt, handleStreamingCompletion, captureToolCall, updateToolCallStatus } from './streaming.js';
import { cleanupMessageProcessing } from './messages.js';

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
    
    // Capture edited tool call arguments if this is an edit submission
    if (responseType === 'edit' && args && window.currentInterrupt?.value?.action_request?.action) {
        const actionRequest = window.currentInterrupt.value.action_request;
        Logger.info('Capturing edited tool call arguments', { 
            toolName: actionRequest.action, 
            originalArgs: actionRequest.args, 
            editedArgs: args 
        });
        
        // Capture the edited tool call arguments
        captureToolCall(actionRequest.action, args, 'interrupt_edit');
    }
    
    // Update tool call status based on decision
    if (window.currentInterrupt?.value?.action_request?.action) {
        const actionRequest = window.currentInterrupt.value.action_request;
        updateToolCallStatus(actionRequest.action, responseType);
    }

    try {
        Logger.info('Current thread ID format', { currentThreadId: getCurrentThreadId() });
        Logger.info('Current interrupt structure', { 
            currentInterrupt: window.currentInterrupt,
            interruptValue: window.currentInterrupt?.value,
            actionRequest: window.currentInterrupt?.value?.action_request
        });
        
        // Use currentThreadId directly since it's already in the correct format
        if (!getCurrentThreadId()) {
            throw new Error('No conversation ID available for resume request');
        }
        
        // Create the input object based on the response type
        let input;
        
        if (responseType === 'edit') {
            input = {
                decision: 'edit',
                args: args
            };
        } else if (responseType === 'accept') {
            input = {
                decision: 'accept'
            };
        } else if (responseType === 'reject') {
            input = {
                decision: 'reject'
            };
        } else {
            // Handle feedback case if needed
            input = {
                decision: 'feedback',
                message: args || 'User feedback'
            };
        }

        const resumePayload = {
            input: input
        };

        Logger.info('Sending resume payload', { resumePayload });

        // Log the full request details for debugging
        Logger.info('Resume request details', {
            url: buildApiUrl(API_CONFIG.URL_TEMPLATES.RESUME_DECISION, { conversation_id: getCurrentThreadId() }),
            method: 'POST',
            payload: resumePayload,
            responseType,
            args
        });

        const requestUrl = buildApiUrl(API_CONFIG.URL_TEMPLATES.RESUME_DECISION, { conversation_id: getCurrentThreadId() });
        const requestOptions = {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream',
                'Authorization': 'Bearer dev-token'
            },
            body: JSON.stringify(resumePayload)
        };
        
        Logger.info('About to send resume request', { 
            url: requestUrl, 
            options: requestOptions,
            headers: requestOptions.headers 
        });
        
        const response = await NetworkManager.fetchWithRetry(requestUrl, requestOptions);

        if (!response.ok) {
            throw new Error(`HTTP error! status: ${response.status}`);
        }

        await handleResumeStream(response);
        
        // Success message is now handled in handleResumeStream after completion

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

async function handleResumeStream(response) {
    Logger.info('Starting resume stream processing', { responseStatus: response.status });
    
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                Logger.info('Resume stream completed (done)');
                break;
            }

            const chunk = decoder.decode(value, { stream: true });
            Logger.info('Received resume stream chunk', { chunkLength: chunk.length, chunk: chunk.substring(0, 100) });
            
            buffer += chunk;
            const lines = buffer.split('\n');
            buffer = lines.pop() || '';

            for (const line of lines) {
                Logger.info('Processing resume line', { line: line.substring(0, 100) });
                
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    Logger.info('Processing resume data', { data: data.substring(0, 100) });
                    
                    if (data === '[DONE]') {
                        Logger.info('Resume stream marked as done');
                        break;
                    }

                    try {
                        if (!data || data.trim() === '') continue;
                        const event = JSON.parse(data);

                        // Use the same event processing logic as regular streaming
                        // Find the last assistant message div to update
                        const lastAssistantMessage = document.querySelector('.assistant-message:last-child');
                        processStreamEvent(event, lastAssistantMessage);
                    } catch (e) {
                        Logger.warn('Failed to parse resume event', { error: e.message });
                    }
                }
            }
        }
    } catch (error) {
        Logger.error('Resume stream processing caught error', { 
            error, 
            errorType: typeof error, 
            errorMessage: error?.message,
            errorStack: error?.stack 
        });
        ErrorHandler.handleError(error, 'Resume stream processing');
        // Clear interrupt state on error as well
        window.currentInterrupt = null;
        const existingInterrupt = document.querySelector('.interrupt-container');
        if (existingInterrupt) {
            existingInterrupt.remove();
        }
        Logger.info('Interrupt state cleared due to resume stream error');
        
        // Clear processing state on error since the workflow is complete
        cleanupMessageProcessing();
    } finally {
        reader.releaseLock();
        
        // Remove the interrupt container after the entire flow is complete
        const existingInterrupt = document.querySelector('.interrupt-container');
        if (existingInterrupt) {
            existingInterrupt.remove();
            Logger.info('Interrupt container removed after resume stream completion');
        }
        
        // Clear interrupt state after container removal
        if (window.currentInterrupt) {
            window.currentInterrupt = null;
            
            // Reset streaming state to clear accumulated content
            resetStreamingStateAfterInterrupt();
            
            Logger.info('Interrupt state cleared after successful resume stream completion');
        }
        
        // Handle streaming completion for resume stream (after interrupt is cleared)
        const lastAssistantMessage = document.querySelector('.assistant-message:last-child');
        if (lastAssistantMessage) {
            handleStreamingCompletion(true, lastAssistantMessage);
        }
        
        // Clear processing state only after the entire workflow is complete
        // This ensures the send button remains disabled until processing is finished
        cleanupMessageProcessing();
        Logger.info('Processing state cleared after resume stream completion');
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
    
    // Clear the streaming content area and replace it with the interrupt UI
    const streamingContent = assistantMessageDiv.querySelector('.streaming-content');
    if (streamingContent) {
        streamingContent.remove();
        Logger.info('Removed streaming content to make room for interrupt UI');
    }
    
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
