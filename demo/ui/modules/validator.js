/**
 * Validation Module
 * Handles all validation logic and utility functions
 */

import { Logger } from './logger.js';

export function extractValidationErrorDetails(errorBody) {
    try {
        if (typeof errorBody === 'string') {
            const parsed = JSON.parse(errorBody);
            return parsed.detail || parsed.message || errorBody;
        } else if (typeof errorBody === 'object') {
            return errorBody.detail || errorBody.message || JSON.stringify(errorBody);
        }
        return errorBody;
    } catch (error) {
        Logger.warn('Failed to extract validation error details', { error: error.message });
        return errorBody;
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

        // Validate UUID format if provided
        if (threadId && !/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(threadId)) {
            throw new Error('Thread ID must be a valid UUID4');
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
