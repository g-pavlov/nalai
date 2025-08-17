/**
 * State Management Module
 * Handles application state and persistence
 */

import { STORAGE_KEYS } from './config.js';
import { Logger } from './logger.js';
import { DOM } from './dom.js';
import { updateStatusIndicators } from './dom.js';

// State variables
let currentThreadId = null;
let fullMessageContent = '';
let isProcessing = false;
let connectionStatus = 'online';

// State getters and setters
export function getCurrentThreadId() { 
    return currentThreadId; 
}

export function setCurrentThreadId(id) { 
    currentThreadId = id; 
}

export function getFullMessageContent() { 
    return fullMessageContent; 
}

export function setFullMessageContent(content) { 
    fullMessageContent = content; 
}

export function getProcessingStatus() { 
    return isProcessing; 
}

export function setProcessing(processing) { 
    isProcessing = processing; 
}

export function getConnectionStatus() { 
    return connectionStatus; 
}

export function setConnectionStatus(status) { 
    connectionStatus = status; 
}

export async function loadSavedState() {
    try {
        // Load settings
        const savedSettings = localStorage.getItem(STORAGE_KEYS.SETTINGS);
        if (savedSettings) {
            const settings = JSON.parse(savedSettings);
            if (settings.streaming !== undefined) {
                DOM.streamingToggle.checked = settings.streaming;
            }
            if (settings.noCache !== undefined) {
                DOM.noCacheToggle.checked = settings.noCache;
            }
            if (settings.model) {
                DOM.modelSelector.value = settings.model;
            }
        }

        updateStatusIndicators();
        
        // Try to load last conversation if it exists
        const lastConversationId = localStorage.getItem('nalai_last_conversation_id');
        if (lastConversationId) {
            try {
                // We'll need to import loadConversation from the conversations module
                // For now, we'll just set the thread ID
                setCurrentThreadId(lastConversationId);
                return true; // Successfully loaded conversation ID
            } catch (error) {
                // Check if it's a 404 error (conversation not found)
                if (error.status === 404) {
                    Logger.info('Last conversation not found (likely due to server restart), proceeding with clean slate', { 
                        conversationId: lastConversationId,
                        error: error.message 
                    });
                    // Clear the invalid conversation ID
                    localStorage.removeItem('nalai_last_conversation_id');
                } else {
                    Logger.warn('Failed to load last conversation due to other error', { error });
                }
                return false; // Failed to load conversation
            }
        }
        
        return false; // No conversation to load
        
    } catch (error) {
        Logger.warn('Failed to load saved state', { error: error.message });
        return false;
    }
}

export function saveSettings() {
    try {
        const settings = {
            streaming: DOM.streamingToggle.checked,
            noCache: DOM.noCacheToggle.checked,
            model: DOM.modelSelector.value,
            timestamp: new Date().toISOString()
        };
        
        localStorage.setItem(STORAGE_KEYS.SETTINGS, JSON.stringify(settings));
    } catch (error) {
        Logger.warn('Failed to save settings', { error: error.message });
    }
}
