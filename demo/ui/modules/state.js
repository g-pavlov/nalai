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
        
        // Don't use localStorage for conversation state - rely on server state only
        // The conversations list will be refreshed on app initialization
        return false; // No conversation to load from localStorage
        
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
