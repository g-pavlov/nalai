/**
 * nalAI Chat Interface JavaScript
 */

// ============================================================================
// CONSTANTS AND CONFIGURATION
// ============================================================================

// API Configuration
const API_CONFIG = {
    BASE_URL: window.location.hostname === 'localhost' ? 'http://localhost:8000' : `http://${window.location.hostname}:8000`,
    URL_TEMPLATES: {
        // Base templates for actual API endpoints
        CONVERSATIONS: '/api/v1/conversations',
        CONVERSATION: '/api/v1/conversations/{conversation_id}',
        RESUME_DECISION: '/api/v1/conversations/{conversation_id}/resume-decision'
    },
    HEADERS: {
        CONTENT_TYPE: 'Content-Type',
        CONTENT_TYPE_VALUE: 'application/json',
        ACCEPT: 'Accept',
        ACCEPT_STREAM: 'text/event-stream',
        NO_CACHE: 'X-No-Cache',
        AUTHORIZATION: 'Authorization',
        AUTHORIZATION_VALUE: 'Bearer dev-token'
    },
    TIMEOUT: 30000, // 30 seconds
    RETRY_ATTEMPTS: 3,
    RETRY_DELAY: 1000 // 1 second
};

/**
 * Generic function to build URLs from templates with variable substitution
 * @param {string} template - URL template with {variable} placeholders
 * @param {Object} variables - Map of variable names to values
 * @returns {string} - Complete URL with variables substituted
 */
function buildApiUrl(template, variables = {}) {
    if (!template) {
        throw new Error('URL template is required');
    }
    
    // Validate that all required variables are provided
    const requiredParams = template.match(/\{([^}]+)\}/g) || [];
    const missingParams = requiredParams.filter(param => {
        const paramName = param.slice(1, -1); // Remove { and }
        return !variables[paramName];
    });
    
    if (missingParams.length > 0) {
        throw new Error(`Missing required URL parameters: ${missingParams.join(', ')}`);
    }
    
    // Substitute variables in template
    let url = template;
    for (const [key, value] of Object.entries(variables)) {
        if (typeof value !== 'string' || value.trim() === '') {
            throw new Error(`Variable '${key}' must be a non-empty string`);
        }
        url = url.replace(`{${key}}`, value.trim());
    }
    
    const fullUrl = API_CONFIG.BASE_URL + url;
    Logger.info('Generated URL from template', { template, variables, fullUrl });
    return fullUrl;
}



// Event Types
const EVENT_TYPES = {
    MESSAGES: 'messages',
    UPDATES: 'updates',
    INTERRUPT: '__interrupt__',
    CALL_MODEL: 'call_model',
    CALL_API: 'call_api',
    CHECK_CACHE: 'check_cache',
    LOAD_API_SUMMARIES: 'load_api_summaries',
    LOAD_API_SPECS: 'load_api_specs',
    SELECT_RELEVANT_APIS: 'select_relevant_apis',
    HUMAN_REVIEW: 'human_review',
    ERROR: 'error'
};

// Message Types
const MESSAGE_TYPES = {
    HUMAN: 'human',
    AI: 'ai',
    TOOL: 'tool',
    AI_CHUNK: 'AIMessageChunk'
};

// UI States
const UI_STATES = {
    LOADING: {
        STREAMING: '🤔 Thinking...',
        PROCESSING: '⏳ Processing...',
        CONNECTING: '🔌 Connecting...',
        RETRYING: '🔄 Retrying...'
    },
    STATUS: {
        ON: 'ON',
        OFF: 'OFF'
    },
    COLORS: {
        SUCCESS: '#059669',
        ERROR: '#dc2626',
        NEUTRAL: '#6b7280',
        WARNING: '#f59e0b'
    }
};

// Storage Keys
const STORAGE_KEYS = {
    THREAD_ID: 'nalai_thread_id',
    SETTINGS: 'nalai_settings',
    ERROR_LOG: 'nalai_error_log'
};

// Error Types
const ERROR_TYPES = {
    NETWORK: 'NETWORK_ERROR',
    API: 'API_ERROR',
    PARSING: 'PARSING_ERROR',
    VALIDATION: 'VALIDATION_ERROR',
    TIMEOUT: 'TIMEOUT_ERROR',
    UNKNOWN: 'UNKNOWN_ERROR'
};

// ============================================================================
// LOGGING AND ERROR HANDLING
// ============================================================================

class Logger {
    static log(level, message, data = null) {
        const timestamp = new Date().toISOString();
        const logEntry = {
            timestamp,
            level,
            message,
            data,
            url: window.location.href,
            userAgent: navigator.userAgent
        };

        console.log(`[${timestamp}] ${level}: ${message}`, data || '');
        
        // Store error logs in localStorage for debugging
        if (level === 'ERROR') {
            this.storeErrorLog(logEntry);
        }
    }

    static info(message, data = null) {
        this.log('INFO', message, data);
    }

    static warn(message, data = null) {
        this.log('WARN', message, data);
    }

    static error(message, data = null) {
        this.log('ERROR', message, data);
    }

    static storeErrorLog(logEntry) {
        try {
            const existingLogs = JSON.parse(localStorage.getItem(STORAGE_KEYS.ERROR_LOG) || '[]');
            existingLogs.push(logEntry);
            
            // Keep only last 50 error logs
            if (existingLogs.length > 50) {
                existingLogs.splice(0, existingLogs.length - 50);
            }
            
            localStorage.setItem(STORAGE_KEYS.ERROR_LOG, JSON.stringify(existingLogs));
        } catch (error) {
            console.error('Failed to store error log:', error);
        }
    }

    static getErrorLogs() {
        try {
            return JSON.parse(localStorage.getItem(STORAGE_KEYS.ERROR_LOG) || '[]');
        } catch (error) {
            console.error('Failed to retrieve error logs:', error);
            return [];
        }
    }

    static clearErrorLogs() {
        localStorage.removeItem(STORAGE_KEYS.ERROR_LOG);
    }
}

class ErrorHandler {
    static createError(type, message, originalError = null) {
        return {
            type,
            message,
            originalError,
            timestamp: new Date().toISOString(),
            stack: originalError?.stack
        };
    }

    static handleError(error, context = '') {
        const errorInfo = this.createError(
            ERROR_TYPES.UNKNOWN,
            error?.message || 'An unknown error occurred',
            error
        );

        Logger.error(`Error in ${context}: ${errorInfo.message}`, errorInfo);
        
        // Show user-friendly error message
        this.showUserError(errorInfo.message, context);
        
        return errorInfo;
    }

    static handleNetworkError(error, context = '') {
        const errorInfo = this.createError(
            ERROR_TYPES.NETWORK,
            'Network connection failed. Please check your internet connection and try again.',
            error
        );

        Logger.error(`Network error in ${context}: ${error?.message || 'Unknown network error'}`, errorInfo);
        this.showUserError(errorInfo.message, context);
        
        return errorInfo;
    }

    static handleApiError(status, statusText, context = '') {
        let message = 'API request failed';
        
        switch (status) {
            case 400:
                message = 'Invalid request. Please check your input and try again.';
                break;
            case 401:
                message = 'Authentication required. Please check your credentials.';
                break;
            case 403:
                message = 'Access denied. You don\'t have permission to perform this action.';
                break;
            case 404:
                message = 'Service not found. Please check if the server is running.';
                break;
            case 422:
                message = `Invalid request format: ${statusText}`;
                break;
            case 429:
                message = 'Too many requests. Please wait a moment and try again.';
                break;
            case 500:
                message = 'Server error. Please try again later.';
                break;
            case 502:
            case 503:
            case 504:
                message = 'Service temporarily unavailable. Please try again later.';
                break;
            default:
                message = `Server error (${status}): ${statusText}`;
        }

        const errorInfo = this.createError(
            ERROR_TYPES.API,
            message,
            { status, statusText }
        );

        Logger.error(`API error in ${context}: ${status} ${statusText}`, errorInfo);
        this.showUserError(errorInfo.message, context);
        
        return errorInfo;
    }

    static handleValidationError(validationDetails, context = '') {
        const message = `Validation Error: ${validationDetails}`;
        
        const errorInfo = this.createError(
            ERROR_TYPES.VALIDATION,
            message,
            { validationDetails }
        );

        Logger.error(`Validation error in ${context}: ${validationDetails}`, errorInfo);
        this.showUserError(errorInfo.message, context);
        
        return errorInfo;
    }

    static handleParsingError(error, data, context = '') {
        const errorInfo = this.createError(
            ERROR_TYPES.PARSING,
            'Failed to parse server response. Please try again.',
            error
        );

        Logger.error(`Parsing error in ${context}: ${error?.message || 'Unknown parsing error'}`, { error, data });
        this.showUserError(errorInfo.message, context);
        
        return errorInfo;
    }

    static handleTimeoutError(context = '') {
        const errorInfo = this.createError(
            ERROR_TYPES.TIMEOUT,
            'Request timed out. Please check your connection and try again.',
            null
        );

        Logger.error(`Timeout error in ${context}`, errorInfo);
        this.showUserError(errorInfo.message, context);
        
        return errorInfo;
    }

    static showUserError(message, context = '') {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'message error-message fade-in';
        errorDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 16px;">⚠️</span>
                <div>
                    <strong>Error${context ? ` (${context})` : ''}:</strong> ${message}
                    <br>
                    <small style="opacity: 0.7;">Please try again or contact support if the problem persists.</small>
                </div>
            </div>
        `;

        DOM.chatContainer.appendChild(errorDiv);
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;

        // Auto-remove error message after 10 seconds
        setTimeout(() => {
            if (errorDiv.parentNode) {
                errorDiv.style.opacity = '0.7';
                setTimeout(() => {
                    if (errorDiv.parentNode) {
                        errorDiv.remove();
                    }
                }, 1000);
            }
        }, 10000);
    }

    static showSuccessMessage(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'message success-message fade-in';
        successDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 16px;">✅</span>
                <div>${message}</div>
            </div>
        `;

        DOM.chatContainer.appendChild(successDiv);
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;

        // Auto-remove success message after 5 seconds
        setTimeout(() => {
            if (successDiv.parentNode) {
                successDiv.style.opacity = '0.7';
                setTimeout(() => {
                    if (successDiv.parentNode) {
                        successDiv.remove();
                    }
                }, 1000);
            }
        }, 5000);
    }

    static showWarningMessage(message) {
        const warningDiv = document.createElement('div');
        warningDiv.className = 'message warning-message fade-in';
        warningDiv.innerHTML = `
            <div style="display: flex; align-items: center; gap: 8px;">
                <span style="font-size: 16px;">⚠️</span>
                <div>${message}</div>
            </div>
        `;

        DOM.chatContainer.appendChild(warningDiv);
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;

        // Auto-remove warning message after 8 seconds
        setTimeout(() => {
            if (warningDiv.parentNode) {
                warningDiv.style.opacity = '0.7';
                setTimeout(() => {
                    if (warningDiv.parentNode) {
                        warningDiv.remove();
                    }
                }, 1000);
            }
        }, 8000);
    }
} 

// ============================================================================
// VALIDATION UTILITIES
// ============================================================================

function normalizeThreadId(threadId) {
    if (!threadId) return null;
    
    // If it's already in user:dev-user:uuid format, return as is
    if (threadId.includes(':')) {
        const parts = threadId.split(':');
        if (parts.length === 3 && parts[0] === 'user' && parts[1] === 'dev-user') {
            return threadId;
        }
    }
    
    // If it's a plain UUID, convert to user:dev-user:uuid format
    try {
        // Validate it's a UUID
        if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(threadId)) {
            return `user:dev-user:${threadId}`;
        }
    } catch (error) {
        Logger.warn('Invalid thread ID format', { threadId, error: error.message });
    }
    
    return null;
}

function extractValidationErrorDetails(errorBody) {
    try {
        // FastAPI validation errors typically have this structure:
        // { "detail": [{ "loc": ["body", "input", "messages", 0, "content"], "msg": "field required", "type": "missing" }] }
        if (errorBody.detail && Array.isArray(errorBody.detail)) {
            const errors = errorBody.detail.map(error => {
                const field = error.loc ? error.loc.join('.') : 'unknown';
                const message = error.msg || 'validation error';
                return `${field}: ${message}`;
            });
            return errors.join('; ');
        }
        
        // Fallback for other error formats
        if (errorBody.detail && typeof errorBody.detail === 'string') {
            return errorBody.detail;
        }
        
        return 'Unknown validation error';
    } catch (error) {
        Logger.warn('Failed to extract validation error details', { error, errorBody });
        return 'Failed to parse validation error details';
    }
}

class Validator {
    static validateMessage(message) {
        if (!message || typeof message !== 'string') {
            throw new Error('Message must be a non-empty string');
        }

        const trimmedMessage = message.trim();
        if (trimmedMessage.length === 0) {
            throw new Error('Message cannot be empty');
        }

        if (trimmedMessage.length > 10000) {
            throw new Error('Message is too long (maximum 10,000 characters)');
        }

        return trimmedMessage;
    }

    static validateThreadId(threadId) {
        if (threadId && typeof threadId !== 'string') {
            throw new Error('Thread ID must be a string');
        }

        if (threadId && threadId.length > 200) {
            throw new Error('Thread ID is too long');
        }

        return threadId;
    }

    static validateApiResponse(response) {
        if (!response) {
            throw new Error('No response received from server');
        }

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}: ${response.statusText}`);
        }

        return response;
    }

    static validateEventData(event) {
        if (!event || typeof event !== 'object') {
            throw new Error('Invalid event data format');
        }

        return event;
    }
}

// ============================================================================
// NETWORK UTILITIES
// ============================================================================

class NetworkManager {
    static async fetchWithTimeout(url, options, timeout = API_CONFIG.TIMEOUT) {
        const controller = new AbortController();
        const timeoutId = setTimeout(() => controller.abort(), timeout);

        Logger.info('NetworkManager.fetchWithTimeout called', { url, options, timeout });

        try {
            const response = await fetch(url, {
                ...options,
                signal: controller.signal
            });
            clearTimeout(timeoutId);
            Logger.info('NetworkManager.fetchWithTimeout succeeded', { 
                url, 
                status: response.status, 
                statusText: response.statusText,
                headers: Object.fromEntries(response.headers.entries())
            });
            return response;
        } catch (error) {
            clearTimeout(timeoutId);
            Logger.error('NetworkManager.fetchWithTimeout failed', { 
                url, 
                error: error.message, 
                errorName: error.name,
                errorStack: error.stack 
            });
            if (error.name === 'AbortError') {
                throw new Error('Request timed out');
            }
            throw error;
        }
    }

    static async fetchWithRetry(url, options, maxRetries = API_CONFIG.RETRY_ATTEMPTS) {
        let lastError;

        for (let attempt = 1; attempt <= maxRetries; attempt++) {
            try {
                Logger.info(`API request attempt ${attempt}/${maxRetries}`, { url });
                
                const response = await this.fetchWithTimeout(url, options);
                
                if (response.ok) {
                    return response;
                }

                // Don't retry on client errors (4xx)
                if (response.status >= 400 && response.status < 500) {
                    const errorMessage = await this.buildErrorMessage(response);
                    throw new Error(errorMessage);
                }

                lastError = new Error(`HTTP ${response.status}: ${response.statusText}`);
                
            } catch (error) {
                lastError = error;
                Logger.warn(`API request attempt ${attempt} failed`, { error: error.message, url });
                
                // Don't retry on client errors (4xx) - exit immediately
                if (error.message.includes('HTTP') && error.message.match(/HTTP [4]\d+/)) {
                    break;
                }
                
                if (attempt < maxRetries) {
                    await this.delay(API_CONFIG.RETRY_DELAY * attempt);
                }
            }
        }

        throw lastError;
    }

    static delay(ms) {
        return new Promise(resolve => setTimeout(resolve, ms));
    }

    static async buildErrorMessage(response) {
        const baseMessage = `HTTP ${response.status}: ${response.statusText}`;
        
        // Only try to extract detailed error info for 422 validation errors
        if (response.status === 422) {
            try {
                const responseClone = response.clone();
                const errorBody = await responseClone.json();
                const validationDetails = extractValidationErrorDetails(errorBody);
                return `${baseMessage} - ${validationDetails}`;
            } catch (parseError) {
                Logger.warn('Failed to parse 422 error response', { parseError: parseError.message });
                return baseMessage;
            }
        }
        
        return baseMessage;
    }

    static isOnline() {
        return navigator.onLine;
    }

    static addOnlineStatusListener(callback) {
        window.addEventListener('online', () => {
            Logger.info('Network connection restored');
            callback(true);
        });

        window.addEventListener('offline', () => {
            Logger.warn('Network connection lost');
            callback(false);
        });
    }
}

// ============================================================================
// DOM ELEMENTS
// ============================================================================

const DOM = {
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

// ============================================================================
// STATE MANAGEMENT
// ============================================================================

let currentThreadId = null;
let fullMessageContent = '';
let isProcessing = false;
let connectionStatus = 'online';

// ============================================================================
// INITIALIZATION
// ============================================================================

function initializeApp() {
    try {
        Logger.info('Initializing nalAI Chat Interface');
        
        // Initialize DOM elements
        initializeDOMElements();
        
        // Configure marked.js
        configureMarked();
        
        // Load saved state
        loadSavedState();
        
        // Setup event listeners
        setupEventListeners();
        
        // Setup network status monitoring
        NetworkManager.addOnlineStatusListener(handleConnectionStatusChange);
        
        // Show welcome message
        showWelcomeMessage();
        
        Logger.info('App initialization completed successfully');
        
    } catch (error) {
        ErrorHandler.handleError(error, 'App initialization');
    }
}

function initializeDOMElements() {
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

function configureMarked() {
    if (typeof marked === 'undefined') {
        throw new Error('Marked.js library not loaded');
    }

    marked.setOptions({
        breaks: true,
        gfm: true,
        sanitize: false,
        smartLists: true,
        smartypants: true
    });
}

function loadSavedState() {
    try {
        // Load and normalize thread ID
        const savedThreadId = localStorage.getItem(STORAGE_KEYS.THREAD_ID);
        if (savedThreadId) {
            const normalizedThreadId = normalizeThreadId(savedThreadId);
            if (normalizedThreadId) {
                currentThreadId = normalizedThreadId;
                // Update localStorage with normalized format if different
                if (normalizedThreadId !== savedThreadId) {
                    localStorage.setItem(STORAGE_KEYS.THREAD_ID, normalizedThreadId);
                }
                Logger.info('Resumed conversation with thread', { 
                    originalThreadId: savedThreadId, 
                    normalizedThreadId 
                });
                showConversationIndicator();
            } else {
                Logger.warn('Invalid saved thread ID format, clearing', { savedThreadId });
                localStorage.removeItem(STORAGE_KEYS.THREAD_ID);
            }
        }

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
        
    } catch (error) {
        Logger.warn('Failed to load saved state', { error: error.message });
    }
}

function saveSettings() {
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

function setupEventListeners() {
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

// ============================================================================
// EVENT HANDLERS
// ============================================================================

function handleKeyPress(event) {
    if (event.key === 'Enter' && !event.shiftKey) {
        event.preventDefault();
        sendMessage();
    }
}

function handleInputChange() {
    const hasContent = DOM.messageInput.value.trim().length > 0;
    DOM.sendButton.disabled = !hasContent || isProcessing;
}

function handleStreamingToggle() {
    updateStreamingStatus();
    saveSettings();
}

function handleNoCacheToggle() {
    updateNoCacheStatus();
    saveSettings();
}

function handleModelChange() {
    saveSettings();
}

function handleConnectionStatusChange(isOnline) {
    connectionStatus = isOnline ? 'online' : 'offline';
    
    if (isOnline) {
        ErrorHandler.showSuccessMessage('Network connection restored');
    } else {
        ErrorHandler.showWarningMessage('Network connection lost. Some features may be unavailable.');
    }
    
    updateConnectionIndicator();
}

function handleBeforeUnload(event) {
    if (isProcessing) {
        event.preventDefault();
        event.returnValue = 'A message is being processed. Are you sure you want to leave?';
        return event.returnValue;
    }
}

function handleGlobalError(event) {
    ErrorHandler.handleError(event.error, 'Global error');
}

function handleUnhandledRejection(event) {
    ErrorHandler.handleError(event.reason, 'Unhandled promise rejection');
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

function updateStreamingStatus() {
    const isEnabled = DOM.streamingToggle.checked;
    DOM.streamingStatus.textContent = isEnabled ? UI_STATES.STATUS.ON : UI_STATES.STATUS.OFF;
    DOM.streamingStatus.style.color = isEnabled ? UI_STATES.COLORS.SUCCESS : UI_STATES.COLORS.NEUTRAL;
}

function updateNoCacheStatus() {
    const isEnabled = DOM.noCacheToggle.checked;
    DOM.noCacheStatus.textContent = isEnabled ? UI_STATES.STATUS.ON : UI_STATES.STATUS.OFF;
    DOM.noCacheStatus.style.color = isEnabled ? UI_STATES.COLORS.ERROR : UI_STATES.COLORS.NEUTRAL;
}

function updateStatusIndicators() {
    updateStreamingStatus();
    updateNoCacheStatus();
    updateConnectionIndicator();
}

// ============================================================================
// SETTINGS PANEL FUNCTIONS
// ============================================================================

function toggleSettings() {
    console.log('toggleSettings called');
    console.log('DOM.settingsPanel:', DOM.settingsPanel);
    console.log('DOM.settingsButton:', DOM.settingsButton);
    
    if (!DOM.settingsPanel || !DOM.settingsButton) {
        console.error('Settings panel elements not found');
        return;
    }
    
    const isActive = DOM.settingsPanel.classList.contains('active');
    console.log('Panel is active:', isActive);
    
    if (isActive) {
        DOM.settingsPanel.classList.remove('active');
        DOM.settingsButton.setAttribute('aria-expanded', 'false');
        console.log('Settings panel closed');
    } else {
        DOM.settingsPanel.classList.add('active');
        DOM.settingsButton.setAttribute('aria-expanded', 'true');
        console.log('Settings panel opened');
    }
}

function handleClickOutside(event) {
    // Close settings panel if clicking outside of it or the settings button
    if (!DOM.settingsPanel.contains(event.target) && 
        !DOM.settingsButton.contains(event.target)) {
        DOM.settingsPanel.classList.remove('active');
        DOM.settingsButton.setAttribute('aria-expanded', 'false');
    }
}

function updateConnectionIndicator() {
    const indicator = document.getElementById('connectionIndicator');
    if (indicator) {
        indicator.className = `status-indicator ${connectionStatus}`;
        indicator.textContent = connectionStatus === 'online' ? '🟢 Online' : '🔴 Offline';
    }
}

function getRequestHeaders(isStreamingEnabled, isNoCacheEnabled) {
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

function buildRequestPayload(message, config) {
    const payload = {
        messages: [{
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

function createAssistantMessageElement() {
    const assistantMessageDiv = document.createElement('div');
    assistantMessageDiv.className = 'message assistant-message fade-in';
    assistantMessageDiv.textContent = '';
    DOM.chatContainer.appendChild(assistantMessageDiv);
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
    return assistantMessageDiv;
}

function updateMessageContent(element, content) {
    // If no element is provided (for resume streams), find the last assistant message
    if (!element) {
        element = DOM.chatContainer.querySelector('.assistant-message:last-child');
        if (!element) {
            Logger.warn('No assistant message element found for content update');
            return;
        }
        Logger.info('Found last assistant message element for resume stream update');
    }
    
    Logger.info('Updating message content', { 
        contentLength: content?.length || 0,
        hasElement: !!element,
        elementClass: element?.className 
    });
    
    try {
        element.innerHTML = marked.parse(content);
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
    } catch (error) {
        ErrorHandler.handleParsingError(error, content, 'Markdown parsing');
        element.textContent = content; // Fallback to plain text
    }
}

function showWelcomeMessage() {
    const welcomeMessage = 'Hello! I\'m nalAI. I can help you with API integration, data processing, and more. What would you like to work on?';
    addMessage(welcomeMessage, 'assistant');
}

function showConversationIndicator() {
    const indicator = document.createElement('div');
    indicator.className = 'conversation-indicator fade-in';
    indicator.textContent = '🔄 Continuing previous conversation...';
    DOM.chatContainer.appendChild(indicator);
}

// ============================================================================
// MESSAGE HANDLING
// ============================================================================

function addMessage(content, type) {
    try {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${type}-message fade-in`;
        
        if (type === 'assistant') {
            updateMessageContent(messageDiv, content);
        } else {
            messageDiv.textContent = content;
        }
        
        DOM.chatContainer.appendChild(messageDiv);
        DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
        
    } catch (error) {
        ErrorHandler.handleError(error, 'Adding message');
    }
}

function startNewConversation() {
    try {
        currentThreadId = null;
        localStorage.removeItem(STORAGE_KEYS.THREAD_ID);
        
        DOM.chatContainer.innerHTML = '';
        showWelcomeMessage();
        
        Logger.info('Started new conversation');
        ErrorHandler.showSuccessMessage('New conversation started');
        
    } catch (error) {
        ErrorHandler.handleError(error, 'Starting new conversation');
    }
}

// ============================================================================
// API COMMUNICATION
// ============================================================================

async function sendMessage() {
    
    if (isProcessing) {
        Logger.warn('Message already being processed', { isProcessing });
        return;
    }

    const message = DOM.messageInput.value.trim();
    
    try {
        // Validate input
        const validatedMessage = Validator.validateMessage(message);
        
        // Check network status
        if (!NetworkManager.isOnline()) {
            ErrorHandler.showUserError('No internet connection. Please check your network and try again.');
            return;
        }

        // Setup UI state
        setupMessageProcessing(validatedMessage);
        
        // Get configuration
        const config = getMessageConfig();
        
        // Create assistant message element
        const assistantMessageDiv = createAssistantMessageElement();
        fullMessageContent = '';

        // Send request
        const response = await sendApiRequest(validatedMessage, config);
        
        // Process response
        await processApiResponse(response, assistantMessageDiv, config.isStreamingEnabled);

    } catch (error) {
        handleMessageError(error);
    } finally {
        cleanupMessageProcessing();
    }
}

function setupMessageProcessing(message) {
    addMessage(message, MESSAGE_TYPES.HUMAN);
    DOM.messageInput.value = '';
    isProcessing = true;
    DOM.sendButton.disabled = true;
    DOM.loading.style.display = 'block';
    
    const config = getMessageConfig();
    DOM.loadingText.textContent = config.isStreamingEnabled ? 
        UI_STATES.LOADING.STREAMING : 
        UI_STATES.LOADING.PROCESSING;
}

function getMessageConfig() {
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

async function sendApiRequest(message, config) {
    let url;
    
    if (currentThreadId) {
        // Continue existing conversation
        url = buildApiUrl(API_CONFIG.URL_TEMPLATES.CONVERSATION, { conversation_id: currentThreadId });
    } else {
        // Create new conversation
        url = buildApiUrl(API_CONFIG.URL_TEMPLATES.CONVERSATIONS);
    }
    
    const requestPayload = buildRequestPayload(message, config);
    const headers = getRequestHeaders(config.isStreamingEnabled, config.isNoCacheEnabled);
    
    Logger.info('Sending API request', { 
        url,
        isStreaming: config.isStreamingEnabled,
        hasThreadId: !!currentThreadId,
        payload: requestPayload
    });

    try {
        const response = await NetworkManager.fetchWithRetry(url, {
            method: 'POST',
            headers,
            body: JSON.stringify(requestPayload)
        });
        
        // If response is not ok, capture the error body for detailed error messages
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            
            // Try to get the error details from the response body
            try {
                const errorBody = await response.text();
                if (errorBody) {
                    try {
                        const errorJson = JSON.parse(errorBody);
                        if (errorJson.detail) {
                            errorMessage += ` - ${errorJson.detail}`;
                        } else if (errorJson.message) {
                            errorMessage += ` - ${errorJson.message}`;
                        } else {
                            errorMessage += ` - ${errorBody}`;
                        }
                    } catch (parseError) {
                        errorMessage += ` - ${errorBody}`;
                    }
                }
            } catch (bodyError) {
                Logger.warn('Could not read error response body', { bodyError });
            }
            
            const error = new Error(errorMessage);
            error.response = response; // Attach response for error handling
            throw error;
        }
        
        return response;
    } catch (error) {
        if (error.message.includes('timed out')) {
            throw ErrorHandler.handleTimeoutError('API request');
        } else if (error.name === 'TypeError' && error.message.includes('fetch')) {
            throw ErrorHandler.handleNetworkError(error, 'API request');
        } else {
            throw error;
        }
    }
}

async function processApiResponse(response, assistantMessageDiv, isStreamingEnabled) {
    try {
        Validator.validateApiResponse(response);
        
        // Handle thread ID
        handleThreadIdResponse(response);

        // Process response based on type
        if (isStreamingEnabled) {
            await handleStreamingResponse(response, assistantMessageDiv);
        } else {
            await handleNonStreamingResponse(response, assistantMessageDiv);
        }

    } catch (error) {
        if (error.message.includes('HTTP')) {
            const status = parseInt(error.message.match(/HTTP (\d+)/)?.[1] || '500');
            // Extract the full error message after the status code
            const fullErrorMatch = error.message.match(/HTTP \d+: (.+)/);
            const statusText = fullErrorMatch ? fullErrorMatch[1] : 'Unknown error';
            throw ErrorHandler.handleApiError(status, statusText, 'API response processing');
        } else {
            throw error;
        }
    }
}

function handleMessageError(error) {
    Logger.error('Message processing failed', { error: error?.message || 'Unknown error' });
    
    // Create error message element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message error-message fade-in';
    errorDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">❌</span>
            <div>
                <strong>Failed to send message:</strong> ${error?.message || 'Unknown error'}
                <br>
                <small style="opacity: 0.7;">Please try again or check your connection.</small>
            </div>
        </div>
    `;
    
    DOM.chatContainer.appendChild(errorDiv);
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
}

function cleanupMessageProcessing() {
    isProcessing = false;
    DOM.sendButton.disabled = false;
    DOM.loading.style.display = 'none';
    handleInputChange(); // Re-enable send button if there's content
}

function handleThreadIdResponse(response) {
    const conversationId = response.headers.get('X-Conversation-ID');
    Logger.info('Received conversation ID from response', { 
        conversationId, 
        conversationIdType: typeof conversationId,
        hasConversationId: !!conversationId,
        currentThreadId,
        willUpdate: conversationId && conversationId !== currentThreadId
    });
    
    if (conversationId && conversationId !== currentThreadId) {
        const normalizedThreadId = normalizeThreadId(conversationId);
        if (normalizedThreadId) {
            currentThreadId = normalizedThreadId;
            localStorage.setItem(STORAGE_KEYS.THREAD_ID, normalizedThreadId);
            Logger.info('New conversation thread started', { 
                originalConversationId: conversationId, 
                normalizedThreadId 
            });
        } else {
            Logger.warn('Failed to normalize conversation ID', { conversationId });
        }
    }
}

// ============================================================================
// STREAMING RESPONSE HANDLING
// ============================================================================

async function handleStreamingResponse(response, assistantMessageDiv) {
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let hasReceivedEvents = false;
    let buffer = '';
    
    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) break;
            
            buffer += decoder.decode(value, { stream: true });
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer
            
            for (const line of lines) {
                if (line.startsWith('data: ')) {
                    const data = line.slice(6);
                    if (data === '[DONE]') {
                        Logger.info('Stream completed with [DONE] event');
                        break;
                    }
                    
                    if (!data || data.trim() === '') continue;
                    
                    try {
                        const event = JSON.parse(data);
                        hasReceivedEvents = true;
                        
                        Validator.validateEventData(event);
                        processStreamEvent(event, assistantMessageDiv);
                        
                    } catch (error) {
                        ErrorHandler.handleParsingError(error, data, 'Stream event parsing');
                    }
                }
            }
        }
        
        handleStreamingCompletion(hasReceivedEvents, assistantMessageDiv);
        
    } catch (error) {
        ErrorHandler.handleError(error, 'Streaming response processing');
    } finally {
        reader.releaseLock();
    }
}

function processStreamEvent(event, assistantMessageDiv) {
    if (Array.isArray(event) && event.length === 2) {
        const [eventType, eventData] = event;
        
        switch (eventType) {
            case EVENT_TYPES.MESSAGES:
                if (Array.isArray(eventData)) {
                    handleMessageEvent(eventData, assistantMessageDiv);
                }
                break;
            case EVENT_TYPES.UPDATES:
                if (typeof eventData === 'object') {
                    handleUpdateEvent(eventData, assistantMessageDiv);
                }
                break;
            case EVENT_TYPES.ERROR:
                handleErrorEvent(eventData, assistantMessageDiv);
                break;
            default:
                Logger.warn('Unknown event type', { eventType, eventData });
        }
    } else if (event.error) {
        // Handle error events that come as objects with error property
        handleErrorEvent(event.error, assistantMessageDiv);
    } else {
        Logger.warn('Unexpected event format', { event });
    }
}

function handleMessageEvent(eventData, assistantMessageDiv) {
    Logger.info('Processing message events', { messageCount: eventData.length });
    
    // Pre-process to check if this is an internal node message
    const isInternalNode = eventData.some(message => 
        message.langgraph_node && message.langgraph_node !== 'call_model'
    );
    
    if (isInternalNode) {
        const nodeName = eventData.find(m => m.langgraph_node)?.langgraph_node;
        Logger.info('Skipped internal node message batch', { 
            node: nodeName, 
            messageCount: eventData.length 
        });
        return; // Skip the entire batch
    }
    
    for (const message of eventData) {
        Logger.info('Processing message', { 
            type: message.type, 
            hasContent: !!message.content,
            contentLength: message.content?.length || 0,
            id: message.id
        });
        
        if (message.type === MESSAGE_TYPES.AI_CHUNK && message.content) {
            fullMessageContent += message.content;
            Logger.info('Updated fullMessageContent with chunk', { 
                chunk: message.content, 
                fullContent: fullMessageContent,
                fullLength: fullMessageContent.length 
            });
            updateMessageContent(assistantMessageDiv, fullMessageContent);
        } else if (message.type === MESSAGE_TYPES.AI && message.content) {
            fullMessageContent = message.content;
            Logger.info('Set fullMessageContent with complete message', { 
                content: message.content,
                length: message.content.length 
            });
            updateMessageContent(assistantMessageDiv, fullMessageContent);
        } else if (message.type === MESSAGE_TYPES.TOOL && message.content) {
            createToolCallElement(assistantMessageDiv, `🔧 Tool Response: ${message.name || 'Unknown tool'}`);
        }
    }
}

function handleUpdateEvent(eventData, assistantMessageDiv) {
    for (const [updateKey, updateValue] of Object.entries(eventData)) {
        switch (updateKey) {
            case EVENT_TYPES.INTERRUPT:
                handleInterruptEvent(updateValue, assistantMessageDiv);
                break;
            case EVENT_TYPES.CALL_MODEL:
                // This is the LLM call - log it for debugging
                Logger.info(`LLM call event: ${updateKey}`, { updateValue });
                handleCallModelEvent(updateValue, assistantMessageDiv);
                break;
            case EVENT_TYPES.CALL_API:
                handleCallApiEvent(updateValue, assistantMessageDiv);
                break;
            case EVENT_TYPES.CHECK_CACHE:
            case EVENT_TYPES.LOAD_API_SUMMARIES:
            case EVENT_TYPES.LOAD_API_SPECS:
            case EVENT_TYPES.SELECT_RELEVANT_APIS:
            case EVENT_TYPES.HUMAN_REVIEW:
                // These are backend processing events, no UI updates needed
                Logger.info(`Backend processing: ${updateKey}`, { updateValue });
                break;
            default:
                Logger.warn('Unknown update key', { updateKey, updateValue });
        }
    }
}

function handleErrorEvent(errorData, assistantMessageDiv) {
    Logger.error('Error event received from server', { errorData });
    
    let errorMessage = 'An error occurred while processing your request.';
    
    // Try to extract meaningful error message from different error formats
    if (typeof errorData === 'string') {
        errorMessage = errorData;
    } else if (errorData && typeof errorData === 'object') {
        if (errorData.message) {
            errorMessage = errorData.message;
        } else if (errorData.error && errorData.error.message) {
            errorMessage = errorData.error.message;
        } else if (errorData.detail) {
            errorMessage = errorData.detail;
        }
    }
    
    // Create error message element
    const errorDiv = document.createElement('div');
    errorDiv.className = 'message error-message fade-in';
    errorDiv.innerHTML = `
        <div style="display: flex; align-items: center; gap: 8px;">
            <span style="font-size: 16px;">❌</span>
            <div>
                <strong>Server Error:</strong> ${errorMessage}
                <br>
                <small style="opacity: 0.7;">Please try again or check your input.</small>
            </div>
        </div>
    `;
    
    // Insert error message after the assistant message
    if (assistantMessageDiv && assistantMessageDiv.parentNode) {
        assistantMessageDiv.parentNode.insertBefore(errorDiv, assistantMessageDiv.nextSibling);
    } else {
        DOM.chatContainer.appendChild(errorDiv);
    }
    
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
    
    // Clear processing state
    cleanupMessageProcessing();
}

function handleInterruptEvent(updateValue, assistantMessageDiv) {
    Logger.info('Interrupt detected', { updateValue });
    
    const interruptInfo = parseInterruptString(updateValue[0]);
    const actionRequest = interruptInfo?.action_request || {};
    
    createInterruptUI(assistantMessageDiv, actionRequest, interruptInfo);
    
    window.currentInterrupt = {
        value: interruptInfo,
        resumable: true
    };
}

function parseInterruptString(interruptString) {
    try {
        const valueMatch = interruptString.match(/value=\[([^\]]+)\]/);
        if (!valueMatch) return null;

        let valueStr = valueMatch[1];
        valueStr = valueStr
            .replace(/'/g, '"')
            .replace(/True/g, 'true')
            .replace(/False/g, 'false')
            .replace(/None/g, 'null');

        return JSON.parse(valueStr);
    } catch (error) {
        Logger.warn('Failed to parse interrupt string, using fallback', { error: error.message });
        return parseInterruptFallback(interruptString);
    }
}

function parseInterruptFallback(interruptString) {
    try {
        const actionMatch = interruptString.match(/'action': '([^']+)'/);
        const argsMatch = interruptString.match(/'args': \{([^}]+)\}/);
        
        return {
            action_request: {
                action: actionMatch ? actionMatch[1] : 'Unknown tool',
                args: argsMatch ? JSON.parse('{' + argsMatch[1].replace(/'/g, '"').replace(/True/g, 'true').replace(/False/g, 'false') + '}') : {}
            }
        };
    } catch (error) {
        Logger.error('Fallback interrupt parsing failed', { error: error.message });
        return {
            action_request: {
                action: 'Unknown tool',
                args: {}
            }
        };
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

function createInterruptUI(assistantMessageDiv, actionRequest, interruptInfo) {
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
        actionButtons += '<button class="interrupt-button accept" onclick="handleInterrupt(\'accept\')">Accept</button>';
    }
    
    if (allowEdit) {
        actionButtons += '<button class="interrupt-button edit" onclick="handleInterrupt(\'edit\')">Edit</button>';
    }
    
    if (allowRespond) {
        actionButtons += '<button class="interrupt-button reject" onclick="showRejectInput()">Reject</button>';
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
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
}

function handleCallModelEvent(updateValue, assistantMessageDiv) {
    if (updateValue.messages) {
        for (const message of updateValue.messages) {
            if (message.type === MESSAGE_TYPES.AI && message.content) {
                fullMessageContent = message.content;
                updateMessageContent(assistantMessageDiv, fullMessageContent);
            }
        }
    }
}

function handleCallApiEvent(updateValue, assistantMessageDiv) {
    Logger.info('Processing call_api update', { updateValue });
    
    for (const message of updateValue.messages) {
        if (message.type === MESSAGE_TYPES.TOOL && message.content) {
            createToolCallElement(assistantMessageDiv, `✅ API Call Completed: ${message.name || 'Unknown tool'}`);
        } else if (message.type === MESSAGE_TYPES.AI && message.content) {
            fullMessageContent = message.content;
            updateMessageContent(assistantMessageDiv, fullMessageContent);
        }
    }
}

function createToolCallElement(assistantMessageDiv, text) {
    const toolCallDiv = document.createElement('div');
    toolCallDiv.className = 'tool-call fade-in';
    toolCallDiv.textContent = text;
    assistantMessageDiv.appendChild(toolCallDiv);
    DOM.chatContainer.scrollTop = DOM.chatContainer.scrollHeight;
}

function handleStreamingCompletion(hasReceivedEvents, assistantMessageDiv) {
    if (!hasReceivedEvents) {
        assistantMessageDiv.textContent = '⚡ Cached response (no streaming events received)';
        assistantMessageDiv.style.fontStyle = 'italic';
        assistantMessageDiv.style.color = UI_STATES.COLORS.NEUTRAL;
    } else if (window.currentInterrupt) {
        Logger.info('Interrupt detected - not overriding UI with final content');
    } else if (fullMessageContent.trim()) {
        updateMessageContent(assistantMessageDiv, fullMessageContent);
    } else {
        assistantMessageDiv.textContent = '⚠️ Response incomplete - please try again';
        assistantMessageDiv.style.color = UI_STATES.COLORS.ERROR;
    }
}

// ============================================================================
// NON-STREAMING RESPONSE HANDLING
// ============================================================================

async function handleNonStreamingResponse(response, assistantMessageDiv) {
    try {
        // Check if response has content
        const responseText = await response.text();
        
        if (!responseText || responseText.trim() === '') {
            assistantMessageDiv.textContent = '⚠️ Empty response from server';
            return;
        }
        
        // Try to parse as JSON
        let result;
        try {
            result = JSON.parse(responseText);
        } catch (parseError) {
            assistantMessageDiv.textContent = '⚠️ Invalid response format from server';
            return;
        }
        
        if (result.output?.messages?.length > 0) {
            const lastAIMessage = findLastAIMessage(result.output.messages);
            
            if (lastAIMessage) {
                updateMessageContent(assistantMessageDiv, lastAIMessage.content);
            } else {
                assistantMessageDiv.textContent = 'No AI response found';
            }
        } else {
            assistantMessageDiv.textContent = 'No response content received';
        }
    } catch (error) {
        ErrorHandler.handleParsingError(error, null, 'Non-streaming response parsing');
    }
}

function findLastAIMessage(messages) {
    for (let i = messages.length - 1; i >= 0; i--) {
        if (messages[i].type === MESSAGE_TYPES.AI && messages[i].content) {
            return messages[i];
        }
    }
    return null;
}

// ============================================================================
// INTERRUPT HANDLING
// ============================================================================

async function handleInterrupt(responseType, args = null) {
    if (!window.currentInterrupt) {
        Logger.error('No current interrupt to handle');
        ErrorHandler.showUserError('No interrupt to handle');
        return;
    }
    
    // Disable all action buttons and show progress
    disableInterruptActions();
    
    // For now, allow all interrupt handling to proceed
    // The main issue was state cleanup, which we've fixed

    Logger.info('Handling interrupt', { responseType, args });

    // Handle edit case - show edit UI instead of sending request
    if (responseType === 'edit' && !args) {
        showEditInterruptUI();
        return;
    }

    try {
        Logger.info('Current thread ID format', { currentThreadId, threadIdType: typeof currentThreadId });
        Logger.info('Current interrupt structure', { 
            currentInterrupt: window.currentInterrupt,
            interruptValue: window.currentInterrupt?.value,
            actionRequest: window.currentInterrupt?.value?.action_request
        });
        
        // Use currentThreadId directly since it's already in the correct format
        if (!currentThreadId) {
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
            url: buildApiUrl(API_CONFIG.URL_TEMPLATES.RESUME_DECISION, { conversation_id: currentThreadId }),
            method: 'POST',
            payload: resumePayload,
            responseType,
            args
        });

        const requestUrl = buildApiUrl(API_CONFIG.URL_TEMPLATES.RESUME_DECISION, { conversation_id: currentThreadId });
        const requestOptions = {
            method: 'POST',
            headers: {
                [API_CONFIG.HEADERS.CONTENT_TYPE]: API_CONFIG.HEADERS.CONTENT_TYPE_VALUE,
                [API_CONFIG.HEADERS.ACCEPT]: API_CONFIG.HEADERS.ACCEPT_STREAM,
                [API_CONFIG.HEADERS.AUTHORIZATION]: API_CONFIG.HEADERS.AUTHORIZATION_VALUE
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
    let resumeContent = '';
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
                        Validator.validateEventData(event);
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

function updateLastAssistantMessage(content) {
    const lastAssistantMessage = DOM.chatContainer.querySelector('.assistant-message:last-child');
    if (lastAssistantMessage) {
        updateMessageContent(lastAssistantMessage, content);
    }
}

function showEditInterruptUI() {
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
            <button class="interrupt-button cancel" onclick="cancelEditInterrupt()">Cancel</button>
            <button class="interrupt-button submit" onclick="submitEditedInterrupt()">Submit</button>
        </div>
    `;

    // Focus on the textarea
    const textarea = document.getElementById('editArgsTextarea');
    if (textarea) {
        textarea.focus();
        textarea.select();
    }
}

function cancelEditInterrupt() {
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

function showRejectInput() {
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
            <button class="interrupt-button cancel" onclick="cancelRejectInput()">Cancel</button>
            <button class="interrupt-button submit" onclick="submitRejectInput()">Submit Rejection</button>
        </div>
    `;

    // Focus on the textarea
    const textarea = document.getElementById('rejectReasonTextarea');
    if (textarea) {
        textarea.focus();
    }
}

function cancelRejectInput() {
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

function submitRejectInput() {
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

function submitEditedInterrupt() {
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

// ============================================================================
// GLOBAL FUNCTIONS (for onclick handlers)
// ============================================================================

// Make functions available globally for HTML onclick handlers
window.sendMessage = sendMessage;
window.startNewConversation = startNewConversation;
window.handleInterrupt = handleInterrupt;
window.cancelEditInterrupt = cancelEditInterrupt;
window.submitEditedInterrupt = submitEditedInterrupt;
window.showRejectInput = showRejectInput;
window.cancelRejectInput = cancelRejectInput;
window.submitRejectInput = submitRejectInput;

// ============================================================================
// STARTUP
// ============================================================================

// Initialize app when DOM is ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initializeApp);
} else {
    initializeApp();
} 