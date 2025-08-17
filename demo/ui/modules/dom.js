/**
 * DOM Management Module
 * Handles all DOM element references and UI updates
 */

import { getConnectionStatus } from './state.js';

export const DOM = {
    chatContainer: null,
    messageInput: null,
    sendButton: null,
    loading: null,
    loadingText: null,
    streamingToggle: null,
    streamingStatus: null,
    noCacheToggle: null,
    noCacheStatus: null,
    modelSelector: null,
    settingsPanel: null,
    settingsButton: null
};

export function initializeDOMElements() {
    DOM.chatContainer = document.getElementById('chatContainer');
    DOM.messageInput = document.getElementById('messageInput');
    DOM.sendButton = document.getElementById('sendButton');
    DOM.loading = document.getElementById('loading');
    DOM.loadingText = document.getElementById('loadingText');
    DOM.streamingToggle = document.getElementById('streamingToggle');
    DOM.streamingStatus = document.getElementById('streamingStatus');
    DOM.noCacheToggle = document.getElementById('noCacheToggle');
    DOM.noCacheStatus = document.getElementById('noCacheStatus');
    DOM.modelSelector = document.getElementById('modelSelector');
    DOM.settingsPanel = document.getElementById('settingsPanel');
    DOM.settingsButton = document.getElementById('settingsButton');

    // Validate required elements
    const requiredElements = [
        'chatContainer', 'messageInput', 'sendButton', 'loading',
        'streamingToggle', 'noCacheToggle', 'modelSelector',
        'settingsPanel', 'settingsButton'
    ];

    for (const elementName of requiredElements) {
        if (!DOM[elementName]) {
            throw new Error(`Required DOM element not found: ${elementName}`);
        }
    }
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

export function updateStatusIndicators() {
    updateStreamingStatus();
    updateNoCacheStatus();
    updateConnectionIndicator();
}

export function updateConnectionIndicator() {
    const indicator = document.getElementById('connectionIndicator');
    if (indicator) {
        const connectionStatus = getConnectionStatus();
        indicator.className = `status-indicator ${connectionStatus}`;
        indicator.textContent = connectionStatus === 'online' ? '🟢 Online' : '�� Offline';
    }
}
