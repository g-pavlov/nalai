/**
 * Error Handling Module
 * Handles all error processing and user-facing error messages
 */

import { ERROR_TYPES, UI_STATES } from './config.js';
import { Logger } from './logger.js';

export class ErrorHandler {
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
            <div class="message-content-layout">
                <span class="message-icon">⚠️</span>
                <div>
                    <strong>Error${context ? ` (${context})` : ''}:</strong> ${message}
                    <br>
                    <small class="message-text-muted">Please try again or contact support if the problem persists.</small>
                </div>
            </div>
        `;

        // We'll need to get DOM.chatContainer from the DOM module
        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.appendChild(errorDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

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
            <div class="message-content-layout">
                <span class="message-icon">✅</span>
                <div>${message}</div>
            </div>
        `;

        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.appendChild(successDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

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

    static showUserSuccess(message) {
        this.showSuccessMessage(message);
    }

    static showWarningMessage(message) {
        const warningDiv = document.createElement('div');
        warningDiv.className = 'message warning-message fade-in';
        warningDiv.innerHTML = `
            <div class="message-content-layout">
                <span class="message-icon">⚠️</span>
                <div>${message}</div>
            </div>
        `;

        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.appendChild(warningDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

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

    static showInfoMessage(message, duration = 3000) {
        const infoDiv = document.createElement('div');
        infoDiv.className = 'message info-message fade-in';
        infoDiv.innerHTML = `
            <div class="message-content-layout">
                <span class="message-icon">ℹ️</span>
                <div>${message}</div>
            </div>
        `;

        const chatContainer = document.getElementById('chatContainer');
        if (chatContainer) {
            chatContainer.appendChild(infoDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Auto-remove info message after specified duration
        setTimeout(() => {
            if (infoDiv.parentNode) {
                infoDiv.style.opacity = '0.7';
                setTimeout(() => {
                    if (infoDiv.parentNode) {
                        infoDiv.remove();
                    }
                }, 1000);
            }
        }, duration);
    }
}
