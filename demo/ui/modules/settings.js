/**
 * Settings Module
 * Handles settings panel and configuration functions
 */

import { API_CONFIG, MESSAGE_TYPES } from './config.js';
import { DOM } from './dom.js';
import { Logger } from './logger.js';

export function toggleSettings() {
    Logger.info('toggleSettings called');
    
    if (!DOM.settingsPanel || !DOM.settingsButton) {
        Logger.error('Settings panel elements not found');
        return;
    }
    
    const isActive = DOM.settingsPanel.classList.contains('active');
    Logger.info('Panel is active:', { isActive });
    
    if (isActive) {
        DOM.settingsPanel.classList.remove('active');
        DOM.settingsButton.setAttribute('aria-expanded', 'false');
        Logger.info('Settings panel closed');
    } else {
        DOM.settingsPanel.classList.add('active');
        DOM.settingsButton.setAttribute('aria-expanded', 'true');
        Logger.info('Settings panel opened');
    }
}

export function handleClickOutside(event) {
    // Close settings panel if clicking outside of it or the settings button
    if (!DOM.settingsPanel.contains(event.target) && 
        !DOM.settingsButton.contains(event.target)) {
        DOM.settingsPanel.classList.remove('active');
        DOM.settingsButton.setAttribute('aria-expanded', 'false');
    }
}

export function getRequestHeaders(isStreamingEnabled, isNoCacheEnabled) {
    const headers = {
        [API_CONFIG.HEADERS.CONTENT_TYPE]: API_CONFIG.HEADERS.CONTENT_TYPE_VALUE,
        [API_CONFIG.HEADERS.AUTHORIZATION]: API_CONFIG.HEADERS.AUTHORIZATION_VALUE
    };
    
    if (isStreamingEnabled) {
        headers[API_CONFIG.HEADERS.ACCEPT] = API_CONFIG.HEADERS.ACCEPT_STREAM;
    }
    
    if (isNoCacheEnabled) {
        headers[API_CONFIG.HEADERS.NO_CACHE] = 'true';
    }
    
    return headers;
}

export function buildRequestPayload(message, config) {
    const payload = {
        input: [{
            content: message,
            type: MESSAGE_TYPES.HUMAN
        }]
    };

    // Add model configuration if available
    if (config && config.selectedModel) {
        payload.model = {
            name: config.selectedModel.name,
            platform: config.selectedModel.platform || config.selectedModel.provider || 'openai'
        };
    }

    return payload;
}

export function getMessageConfig() {
    let selectedModel;
    try {
        selectedModel = JSON.parse(DOM.modelSelector.value);
    } catch (error) {
        // Fallback to default model if parsing fails
        selectedModel = { name: "gpt-4.1o", platform: "openai" };
    }
    
    return {
        selectedModel,
        isStreamingEnabled: DOM.streamingToggle.checked,
        isNoCacheEnabled: DOM.noCacheToggle.checked
    };
}
