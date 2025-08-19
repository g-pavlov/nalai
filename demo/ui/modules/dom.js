/**
 * DOM Management Module
 * Handles all DOM element references and UI updates
 */

import { getConnectionStatus } from './state.js';

export const DOM = {
    chatContainer: null,
    messageInput: null,
    sendButton: null,

    streamingToggle: null,
    streamingStatus: null,
    noCacheToggle: null,
    noCacheStatus: null,
    debugToggle: null,
    debugStatus: null,
    jsonFormatToggle: null,
    jsonFormatStatus: null,
    modelSelector: null,
    settingsPanel: null,
    settingsButton: null,
    conversationsPanel: null,
    conversationsList: null,
    conversationsLoading: null,
    conversationsEmpty: null,
    conversationsError: null
};

export function initializeDOMElements() {
    DOM.chatContainer = document.getElementById('chatContainer');
    DOM.messageInput = document.getElementById('messageInput');
    DOM.sendButton = document.getElementById('sendButton');

    DOM.streamingToggle = document.getElementById('streamingToggle');
    DOM.streamingStatus = document.getElementById('streamingStatus');
    DOM.noCacheToggle = document.getElementById('noCacheToggle');
    DOM.noCacheStatus = document.getElementById('noCacheStatus');
    DOM.debugToggle = document.getElementById('debugToggle');
    DOM.debugStatus = document.getElementById('debugStatus');
    DOM.jsonFormatToggle = document.getElementById('jsonFormatToggle');
    DOM.jsonFormatStatus = document.getElementById('jsonFormatStatus');
    DOM.modelSelector = document.getElementById('modelSelector');
    DOM.settingsPanel = document.getElementById('settingsPanel');
    DOM.settingsButton = document.getElementById('settingsButton');
    DOM.conversationsPanel = document.getElementById('conversationsPanel');
    DOM.conversationsList = document.getElementById('conversationsList');
    DOM.conversationsLoading = document.getElementById('conversationsLoading');
    DOM.conversationsEmpty = document.getElementById('conversationsEmpty');
    DOM.conversationsError = document.getElementById('conversationsError');

    // Validate required elements
    const requiredElements = [
        'chatContainer', 'messageInput', 'sendButton',
        'streamingToggle', 'noCacheToggle', 'debugToggle', 'jsonFormatToggle', 'modelSelector',
        'settingsPanel', 'settingsButton', 'conversationsPanel',
        'conversationsList', 'conversationsLoading', 'conversationsEmpty', 'conversationsError'
    ];

    for (const elementName of requiredElements) {
        if (!DOM[elementName]) {
            throw new Error(`Required DOM element not found: ${elementName}`);
        }
    }

    // Initialize send button state - disable it if input is empty
    const hasContent = DOM.messageInput.value.trim().length > 0;
    DOM.sendButton.disabled = !hasContent;
}

export function updateStreamingStatus() {
    const isEnabled = DOM.streamingToggle.checked;
    DOM.streamingStatus.textContent = isEnabled ? 'ON' : 'OFF';
    DOM.streamingStatus.style.color = isEnabled ? '#059669' : '#6b7280';
}

export function updateNoCacheStatus() {
    const isEnabled = DOM.noCacheToggle.checked;
    DOM.noCacheStatus.textContent = isEnabled ? 'ON' : 'OFF';
    DOM.noCacheStatus.style.color = isEnabled ? '#dc2626' : '#6b7280';
}

export function updateDebugStatus() {
    const isEnabled = DOM.debugToggle.checked;
    DOM.debugStatus.textContent = isEnabled ? 'ON' : 'OFF';
    DOM.debugStatus.style.color = isEnabled ? '#f59e0b' : '#6b7280';
}

export function updateJsonFormatStatus() {
    const isEnabled = DOM.jsonFormatToggle.checked;
    DOM.jsonFormatStatus.textContent = isEnabled ? 'ON' : 'OFF';
    DOM.jsonFormatStatus.style.color = isEnabled ? '#2563eb' : '#6b7280';
}

export function updateStatusIndicators() {
    updateStreamingStatus();
    updateNoCacheStatus();
    updateDebugStatus();
    updateJsonFormatStatus();
    updateConnectionIndicator();
}

export function updateConnectionIndicator() {
    const indicator = document.getElementById('connectionIndicator');
    if (indicator) {
        const connectionStatus = getConnectionStatus();
        indicator.className = `status-indicator ${connectionStatus}`;
        indicator.textContent = connectionStatus === 'online' ? '🟢 Online' : '🔴 Offline';
    }
}
