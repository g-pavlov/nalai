/**
 * Network Module
 * Handles all network communication and HTTP requests
 */

import { API_CONFIG } from './config.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { extractValidationErrorDetails } from './validator.js';

export class NetworkManager {
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
