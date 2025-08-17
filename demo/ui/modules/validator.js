/**
 * Validation Module
 * Handles all validation logic and utility functions
 */

import { Logger } from './logger.js';

export function normalizeThreadId(threadId) {
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

export function extractValidationErrorDetails(errorBody) {
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

export class Validator {
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
