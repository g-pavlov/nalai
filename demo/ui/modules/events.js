/**
 * Events Module
 * Handles all event listeners and event processing
 */

import { DOM } from './dom.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { setConnectionStatus, getProcessingStatus } from './state.js';
import { saveSettings } from './state.js';
import { toggleSettings, handleClickOutside } from './settings.js';

// Placeholder functions that will be implemented in other modules
let sendMessage = () => console.log('sendMessage not implemented yet');

// Implement handleInputChange function
function handleInputChange() {
    const hasContent = DOM.messageInput.value.trim().length > 0;
    DOM.sendButton.disabled = !hasContent || getProcessingStatus();
}

export function setupEventListeners() {
    // Input events
    DOM.messageInput.addEventListener('keypress', handleKeyPress);
    DOM.messageInput.addEventListener('input', handleInputChange);
    
    // Button events
    DOM.sendButton.addEventListener('click', sendMessage);
    
    // Toggle events
    DOM.streamingToggle.addEventListener('change', handleStreamingToggle);
    DOM.noCacheToggle.addEventListener('change', handleNoCacheToggle);
    DOM.modelSelector.addEventListener('change', handleModelChange);
    
    // Settings panel events
    document.addEventListener('click', handleClickOutside);
    
    // Global events
    window.addEventListener('beforeunload', handleBeforeUnload);
    
    // Error handling
    window.addEventListener('error', handleGlobalError);
    window.addEventListener('unhandledrejection', handleUnhandledRejection);
}

export function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

export function handleStreamingToggle() {
    // This will be implemented when we connect to the DOM module
    console.log('Streaming toggle changed');
    saveSettings();
}

export function handleNoCacheToggle() {
    // This will be implemented when we connect to the DOM module
    console.log('No cache toggle changed');
    saveSettings();
}

export function handleModelChange() {
    saveSettings();
}

export function handleConnectionStatusChange(isOnline) {
    setConnectionStatus(isOnline ? 'online' : 'offline');
    
    if (isOnline) {
        ErrorHandler.showSuccessMessage('Network connection restored');
    } else {
        ErrorHandler.showWarningMessage('Network connection lost. Some features may be unavailable.');
    }
    
    // We'll need to update the connection indicator
    console.log('Connection status changed:', isOnline);
}

export function handleBeforeUnload(event) {
    // We'll need to check if processing from state module
    if (getProcessingStatus()) {
        event.preventDefault();
        event.returnValue = 'A message is being processed. Are you sure you want to leave?';
        return event.returnValue;
    }
}

export function handleGlobalError(event) {
    ErrorHandler.handleError(event.error, 'Global error');
}

export function handleUnhandledRejection(event) {
    ErrorHandler.handleError(event.reason, 'Unhandled promise rejection');
}

// Function to set the sendMessage function from the API module
export function setSendMessageFunction(fn) {
    sendMessage = fn;
}

// Export the handleInputChange function so it can be used elsewhere
export { handleInputChange };

// Function to set the handleInputChange function
export function setHandleInputChangeFunction(fn) {
    handleInputChange = fn;
}
