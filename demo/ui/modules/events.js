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
let sendMessage = () => {};

// Implement handleInputChange function
function handleInputChange() {
    const hasContent = DOM.messageInput.value.trim().length > 0;
    DOM.sendButton.disabled = !hasContent;
}

// Implement handleSendClick function
function handleSendClick() {
    if (DOM.messageInput.value.trim()) {
        sendMessage();
    }
}

// Implement handleKeyPress function
function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        handleSendClick();
    }
}

// Implement handleStreamingToggle function
function handleStreamingToggle() {
    const isStreamingEnabled = DOM.streamingToggle.checked;
    saveSettings({ streamingEnabled: isStreamingEnabled });
}

// Implement handleNoCacheToggle function
function handleNoCacheToggle() {
    const noCacheEnabled = DOM.noCacheToggle.checked;
    saveSettings({ noCacheEnabled: noCacheEnabled });
}

// Implement handleModelChange function
function handleModelChange() {
    saveSettings();
}

// Implement handleConnectionStatusChange function
function handleConnectionStatusChange(isOnline) {
    setConnectionStatus(isOnline);
}

export function setupEventListeners() {
    // Input events
    DOM.messageInput.addEventListener('keypress', handleKeyPress);
    DOM.messageInput.addEventListener('input', handleInputChange);
    
    // Button events
    DOM.sendButton.addEventListener('click', handleSendClick);
    
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
