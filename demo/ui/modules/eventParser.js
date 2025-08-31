/**
 * Event Parser Module
 * Handles parsing and processing of Server-Sent Events (SSE) streams
 * 
 * Note: We use fetch() with manual parsing instead of EventSource because:
 * - EventSource only supports GET requests
 * - We need POST requests with custom headers and authentication
 * - Our API requires request bodies with message content
 */

import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';

/**
 * Parse SSE stream and route events to appropriate handlers
 * Uses native ReadableStream API for efficient streaming
 * @param {ReadableStream} response - The streaming response
 * @param {Function} eventHandler - Function to handle parsed events
 * @param {Function} onComplete - Function called when stream completes
 * @param {Function} onError - Function called on error
 */
export async function parseSSEStream(response, eventHandler, onComplete, onError) {
    // Use native ReadableStream for efficient streaming
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    try {
        while (true) {
            const { done, value } = await reader.read();
            if (done) {
                Logger.info('SSE stream completed (done)');
                break;
            }

            // Use native TextDecoder for efficient decoding
            const chunk = decoder.decode(value, { stream: true });
            Logger.info('Received SSE chunk', { chunkLength: chunk.length, chunk: chunk.substring(0, 100) });
            
            buffer += chunk;
            const lines = buffer.split('\n');
            buffer = lines.pop() || ''; // Keep incomplete line in buffer

            // Process complete lines
            for (const line of lines) {
                await processSSELine(line, eventHandler);
            }
        }
        
        if (onComplete) {
            onComplete();
        }
        
    } catch (error) {
        Logger.error('SSE stream parsing error', { 
            error, 
            errorType: typeof error, 
            errorMessage: error?.message,
            errorStack: error?.stack 
        });
        
        if (onError) {
            onError(error);
        } else {
            ErrorHandler.handleError(error, 'SSE stream parsing');
        }
    } finally {
        reader.releaseLock();
    }
}

/**
 * Process a single SSE line according to SSE specification
 * Handles data, event, id, and retry fields as per RFC 7230
 * @param {string} line - The SSE line to process
 * @param {Function} eventHandler - Function to handle parsed events
 */
async function processSSELine(line, eventHandler) {
    // Skip empty lines and comments
    if (!line || line.trim() === '' || line.startsWith(':')) {
        return;
    }
    
    Logger.info('Processing SSE line', { line: line.substring(0, 100) });
    
    // Parse SSE fields according to specification
    const fields = parseSSEFields(line);
    
    // Handle data field (our main content)
    if (fields.data) {
        Logger.info('Processing SSE data', { data: fields.data.substring(0, 100) });
        
        if (fields.data === '[DONE]') {
            Logger.info('SSE stream marked as done');
            return;
        }

        if (!fields.data || fields.data.trim() === '') {
            return;
        }

        try {
            const eventData = JSON.parse(fields.data);
            
            if (eventHandler) {
                await eventHandler(eventData);
            }
            
        } catch (error) {
            Logger.warn('Failed to parse SSE event', { error: error.message, data: fields.data });
            ErrorHandler.handleParsingError(error, fields.data, 'SSE event parsing');
        }
    }
    
    // Handle other SSE fields if needed (event, id, retry)
    if (fields.event && fields.event !== 'message') {
        Logger.info('Received SSE event', { event: fields.event });
    }
    
    if (fields.id) {
        Logger.info('Received SSE id', { id: fields.id });
    }
}

/**
 * Parse SSE fields according to SSE specification
 * @param {string} line - The SSE line to parse
 * @returns {Object} Parsed SSE fields
 */
function parseSSEFields(line) {
    const fields = {};
    
    // Split by field separator and process each field
    const fieldLines = line.split('\n');
    
    for (const fieldLine of fieldLines) {
        if (!fieldLine || fieldLine.trim() === '') continue;
        
        const colonIndex = fieldLine.indexOf(':');
        if (colonIndex === -1) continue;
        
        const fieldName = fieldLine.substring(0, colonIndex).trim();
        let fieldValue = fieldLine.substring(colonIndex + 1).trim();
        
        // Remove leading space if present (per SSE spec)
        if (fieldValue.startsWith(' ')) {
            fieldValue = fieldValue.substring(1);
        }
        
        // Handle field-specific logic
        switch (fieldName) {
            case 'data':
                // Accumulate data fields (multiple data fields are concatenated)
                fields.data = fields.data ? fields.data + '\n' + fieldValue : fieldValue;
                break;
            case 'event':
                fields.event = fieldValue;
                break;
            case 'id':
                fields.id = fieldValue;
                break;
            case 'retry':
                const retryValue = parseInt(fieldValue, 10);
                if (!isNaN(retryValue)) {
                    fields.retry = retryValue;
                }
                break;
        }
    }
    
    return fields;
}

/**
 * Route SSE events to state machine
 * @param {Object} eventData - The parsed event data
 */
export async function routeEventToStateMachine(eventData) {
    const lastAssistantMessage = document.querySelector('.assistant-message:last-child');
    
    if (lastAssistantMessage && lastAssistantMessage.stateMachine && eventData.event) {
        lastAssistantMessage.stateMachine.handleEvent(eventData.event, eventData);
    } else {
        Logger.warn('No state machine found for SSE event processing', { 
            hasMessage: !!lastAssistantMessage,
            hasStateMachine: !!(lastAssistantMessage && lastAssistantMessage.stateMachine),
            hasEvent: !!eventData.event
        });
    }
}
