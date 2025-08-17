/**
 * Logging Module
 * Handles all logging functionality including error storage
 */

import { STORAGE_KEYS } from './config.js';

export class Logger {
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
