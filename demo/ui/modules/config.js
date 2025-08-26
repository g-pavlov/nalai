/**
 * Configuration and Constants Module
 * Contains all configuration constants and utility functions
 */

// API Configuration
export const API_CONFIG = {
    BASE_URL: window.location.hostname === 'localhost' ? 'http://localhost:8000' : `http://${window.location.hostname}:8000`,
    URL_TEMPLATES: {
        // Base templates for actual API endpoints
        CONVERSATIONS: '/api/v1/conversations',
        CONVERSATION: '/api/v1/conversations/{conversation_id}',
        MESSAGES: '/api/v1/messages',
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

// Event Types
export const EVENT_TYPES = {
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
export const MESSAGE_TYPES = {
    HUMAN: 'human',
    AI: 'ai',
    TOOL: 'tool',
    AI_CHUNK: 'AIMessageChunk'
};

// UI States
export const UI_STATES = {
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
export const STORAGE_KEYS = {
    SETTINGS: 'nalai_settings',
    ERROR_LOG: 'nalai_error_log'
};

// Error Types
export const ERROR_TYPES = {
    NETWORK: 'NETWORK_ERROR',
    API: 'API_ERROR',
    PARSING: 'PARSING_ERROR',
    VALIDATION: 'VALIDATION_ERROR',
    TIMEOUT: 'TIMEOUT_ERROR',
    UNKNOWN: 'UNKNOWN_ERROR'
};

/**
 * Generic function to build URLs from templates with variable substitution
 * @param {string} template - URL template with {variable} placeholders
 * @param {Object} variables - Map of variable names to values
 * @returns {string} - Complete URL with variables substituted
 */
export function buildApiUrl(template, variables = {}) {
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
    console.log('Generated URL from template', { template, variables, fullUrl });
    return fullUrl;
}
