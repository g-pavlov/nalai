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
import { processStreamEvent } from './streaming.js';

export async function handleInterrupt(responseType, args = null) {
    if (!window.currentInterrupt) {
        Logger.error('No current interrupt to handle');
        ErrorHandler.showUserError('No interrupt to handle');
        return;
    }
    
    // Disable all action buttons and show progress
    disableInterruptActions();
    
    Logger.info('Handling interrupt', { responseType, args });

    // Handle edit case - show edit UI instead of sending request
    if (responseType === 'edit' && !args) {
        showEditInterruptUI();
        return;
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
            // If feedback is provided, treat as feedback decision, otherwise as reject
            if (args && args.trim()) {
                input = {
                    decision: 'feedback',
                    message: args
                };
            } else {
                input = {
                    decision: 'reject'
                };
            }
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
                        processStreamEvent(event, null); // Pass null for assistantMessageDiv since we're updating the last message
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
    } finally {
        reader.releaseLock();
        
        // Clear interrupt state after successful completion
        if (window.currentInterrupt) {
            window.currentInterrupt = null;
            const existingInterrupt = document.querySelector('.interrupt-container');
            if (existingInterrupt) {
                existingInterrupt.remove();
            }
            Logger.info('Interrupt state cleared after successful resume stream completion');
            ErrorHandler.showSuccessMessage('Interrupt handled successfully');
        }
    }
}

function disableInterruptActions() {
    const interruptContainer = document.querySelector('.interrupt-container');
    if (!interruptContainer) return;
    
    // Disable all buttons
    const buttons = interruptContainer.querySelectorAll('.interrupt-button');
    buttons.forEach(button => {
        button.disabled = true;
        button.style.opacity = '0.6';
        button.style.cursor = 'not-allowed';
    });
    
    // Add progress indicator
    const actionsDiv = interruptContainer.querySelector('.interrupt-actions');
    if (actionsDiv) {
        const progressDiv = document.createElement('div');
        progressDiv.className = 'interrupt-progress';
        progressDiv.innerHTML = `
            <div class="progress-spinner"></div>
            <span>Processing...</span>
        `;
        actionsDiv.appendChild(progressDiv);
    }
}

function enableInterruptActions() {
    const interruptContainer = document.querySelector('.interrupt-container');
    if (!interruptContainer) return;
    
    // Re-enable all buttons
    const buttons = interruptContainer.querySelectorAll('.interrupt-button');
    buttons.forEach(button => {
        button.disabled = false;
        button.style.opacity = '1';
        button.style.cursor = 'pointer';
    });
    
    // Remove progress indicator
    const progressDiv = interruptContainer.querySelector('.interrupt-progress');
    if (progressDiv) {
        progressDiv.remove();
    }
}

export function createInterruptUI(assistantMessageDiv, actionRequest, interruptInfo) {
    // Remove any existing interrupt UI first
    const existingInterrupt = document.querySelector('.interrupt-container');
    if (existingInterrupt) {
        existingInterrupt.remove();
        Logger.info('Removed existing interrupt UI before creating new one');
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
        actionButtons += '<button class="interrupt-button accept" onclick="handleInterrupt(\'accept\')" title="Accept and execute this tool call">Accept</button>';
    }
    
    if (allowEdit) {
        actionButtons += '<button class="interrupt-button edit" onclick="handleInterrupt(\'edit\')" title="Edit the tool arguments before execution">Edit</button>';
    }
    
    if (allowRespond) {
        actionButtons += '<button class="interrupt-button reject" onclick="showRejectInput()" title="Reject this tool call with optional reason">Reject</button>';
    }
    
    // If no actions are allowed, show a message
    if (!actionButtons) {
        actionButtons = '<div class="interrupt-no-actions">No actions available for this interrupt</div>';
    }
    
    interruptDiv.innerHTML = `
        <div class="interrupt-title">🔒 Human Review Required</div>
        <div class="interrupt-details">
            <div><strong>Tool:</strong> ${actionRequest.action || 'Unknown'}</div>
            <div><strong>Arguments:</strong></div>
            <pre style="background: #f3f4f6; padding: 8px; border-radius: 4px; margin: 4px 0; font-size: 12px; overflow-x: auto;">${JSON.stringify(actionRequest.args || {}, null, 2)}</pre>
            ${interruptInfo?.description ? `<div class="interrupt-description">${interruptInfo.description}</div>` : ''}
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
        <div class="interrupt-title">✏️ Edit Tool Arguments</div>
        <div class="interrupt-details">
            <div><strong>Tool:</strong> ${actionRequest.action || 'Unknown'}</div>
            <div><strong>Edit Arguments:</strong></div>
            <textarea 
                id="editArgsTextarea" 
                class="edit-args-textarea"
                placeholder="Enter JSON arguments..."
            >${JSON.stringify(actionRequest.args || {}, null, 2)}</textarea>
            <div class="edit-validation" id="editValidation"></div>
        </div>
        <div class="interrupt-actions">
            <button class="interrupt-button cancel" onclick="cancelEditInterrupt()" title="Cancel editing and return to original interrupt">Cancel</button>
            <button class="interrupt-button submit" onclick="submitEditedInterrupt()" title="Submit the edited arguments">Submit</button>
        </div>
    `;

    // Focus on the textarea
    const textarea = document.getElementById('editArgsTextarea');
    if (textarea) {
        textarea.focus();
        textarea.select();
    }
}

export function showRejectInput() {
    if (!window.currentInterrupt) {
        Logger.error('No current interrupt to reject');
        return;
    }

    // Find the existing interrupt container
    const interruptContainer = document.querySelector('.interrupt-container');
    if (!interruptContainer) {
        Logger.error('No interrupt container found');
        return;
    }

    // Replace the interrupt UI with reject input UI
    interruptContainer.innerHTML = `
        <div class="interrupt-title">❌ Reject Tool Call</div>
        <div class="interrupt-details">
            <div><strong>Rejection reason (optional):</strong></div>
            <textarea 
                id="rejectReasonTextarea" 
                class="reject-reason-textarea"
                placeholder="Enter rejection reason (optional)..."
                rows="3"
            ></textarea>
            <div class="reject-validation" id="rejectValidation"></div>
        </div>
        <div class="interrupt-actions">
            <button class="interrupt-button cancel" onclick="cancelRejectInput()" title="Cancel rejection and return to original interrupt">Cancel</button>
            <button class="interrupt-button submit" onclick="submitRejectInput()" title="Submit the rejection with optional reason">Submit Rejection</button>
        </div>
    `;

    // Focus on the textarea
    const textarea = document.getElementById('rejectReasonTextarea');
    if (textarea) {
        textarea.focus();
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

export function cancelRejectInput() {
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

export function submitRejectInput() {
    if (!window.currentInterrupt) {
        Logger.error('No current interrupt to reject');
        return;
    }

    const textarea = document.getElementById('rejectReasonTextarea');
    const validationDiv = document.getElementById('rejectValidation');
    
    if (!textarea) {
        Logger.error('Reject reason textarea not found');
        return;
    }

    const rejectReason = textarea.value.trim();
    
    // Clear any previous validation errors
    validationDiv.innerHTML = '';
    validationDiv.className = 'reject-validation';
    
    Logger.info('Submitting reject interrupt', { rejectReason, hasFeedback: !!rejectReason });
    
    // Submit the reject interrupt - handleInterrupt will determine if it's reject or feedback
    handleInterrupt('reject', rejectReason);
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
        // Parse the edited JSON
        const editedArgs = JSON.parse(textarea.value.trim());
        
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
