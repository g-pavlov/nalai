/**
 * Tool Calls Module
 * Handles the display and interaction of tool calls indicators and panels
 */

import { Logger } from './logger.js';
import { isJsonFormatEnabled } from './settings.js';

/**
 * Creates a tool calls indicator for a message
 * @param {number} toolCount - Number of tool calls
 * @param {Array} toolCalls - Array of tool call objects
 * @returns {HTMLElement} - The indicator element
 */
export function createToolCallsIndicator(toolCount, toolCalls = []) {
    if (!toolCount || toolCount === 0) {
        return null;
    }

    const indicator = document.createElement('span');
    indicator.className = 'message-tools-indicator';
    indicator.textContent = `Tools called (${toolCount})`;
    
    // Add click handler to toggle tools panel
    indicator.addEventListener('click', (e) => {
        e.preventDefault();
        e.stopPropagation();
        toggleToolsPanel(indicator, toolCalls);
    });

    return indicator;
}

/**
 * Toggles the tools panel for a message
 * @param {HTMLElement} indicator - The indicator element
 * @param {Array} toolCalls - Array of tool call objects
 */
function toggleToolsPanel(indicator, toolCalls) {
    const messageDiv = indicator.closest('.message');
    if (!messageDiv) {
        Logger.warn('Could not find parent message for tools indicator');
        return;
    }

    let toolsPanel = messageDiv.querySelector('.tools-panel');
    
    if (!toolsPanel) {
        // Create tools panel if it doesn't exist
        toolsPanel = createToolsPanel(toolCalls);
        messageDiv.appendChild(toolsPanel);
    }

    const isExpanded = toolsPanel.classList.contains('expanded');
    
    if (isExpanded) {
        // Collapse panel
        toolsPanel.classList.remove('expanded');
        setTimeout(() => {
            if (!toolsPanel.classList.contains('expanded')) {
                toolsPanel.remove();
            }
        }, 300); // Match transition duration
    } else {
        // Expand panel
        toolsPanel.classList.add('expanded');
    }

    Logger.info('Toggled tools panel', { 
        isExpanded: !isExpanded, 
        toolCount: toolCalls.length 
    });
}

/**
 * Creates a tools panel with tool call details
 * @param {Array} toolCalls - Array of tool call objects
 * @returns {HTMLElement} - The tools panel element
 */
function createToolsPanel(toolCalls) {
    const panel = document.createElement('div');
    panel.className = 'tools-panel';
    
    const toolCallsHTML = toolCalls.map(toolCall => `
        <div class="tool-call-item">
            <div class="tool-call-header">
                <div class="tool-call-name">${toolCall.name || 'Unknown tool'}</div>
                <div class="tool-call-status ${getToolCallStatusClass(toolCall)}">${getToolCallStatus(toolCall)}</div>
            </div>
            <div class="tool-call-section">
                <div class="tool-call-section-title">Arguments</div>
                <div class="tool-call-args">${formatToolArgs(toolCall.args)}</div>
            </div>
            ${toolCall.content ? `
                <div class="tool-call-section">
                    <div class="tool-call-section-title">Result</div>
                    <div class="tool-call-response">${formatToolResponse(toolCall.content)}</div>
                </div>
            ` : ''}
            ${toolCall.response && !toolCall.content ? `
                <div class="tool-call-section">
                    <div class="tool-call-section-title">Response</div>
                    <div class="tool-call-response">${formatToolResponse(toolCall.response)}</div>
                </div>
            ` : ''}
        </div>
    `).join('');
    
    panel.innerHTML = toolCallsHTML;
    
    return panel;
}

/**
 * Gets the status of a tool call
 * @param {Object} toolCall - Tool call object
 * @returns {string} - Status string
 */
function getToolCallStatus(toolCall) {
    // Simple mapping from status to display text
    const statusMap = {
        'pending': 'Pending',
        'completed': 'Completed',
        'rejected': 'Rejected',
        'confirmed': 'Confirmed',
        'error': 'Error'
    };
    
    return statusMap[toolCall.status] || 'Unknown';
}

/**
 * Gets the CSS class for tool call status
 * @param {Object} toolCall - Tool call object
 * @returns {string} - CSS class name
 */
function getToolCallStatusClass(toolCall) {
    // Simple mapping from status to CSS class
    const statusClassMap = {
        'pending': 'pending',
        'completed': 'completed',
        'rejected': 'rejected',
        'confirmed': 'confirmed',
        'error': 'error'
    };
    
    return statusClassMap[toolCall.status] || 'unknown';
}

/**
 * Formats tool arguments for display
 * @param {Object} args - Tool arguments
 * @returns {string} - Formatted arguments string
 */
function formatToolArgs(args) {
    if (!args || Object.keys(args).length === 0) {
        return 'No arguments';
    }
    
    try {
        return JSON.stringify(args, null, 2);
    } catch (error) {
        Logger.warn('Failed to format tool args', { error, args });
        return String(args);
    }
}

/**
 * Formats tool response for display
 * @param {Object} response - Tool response
 * @returns {string} - Formatted response string
 */
function formatToolResponse(response) {
    if (!response) {
        return 'No response';
    }
    
    // Check if JSON formatting is enabled
    const jsonFormatEnabled = isJsonFormatEnabledLocal();
    
    try {
        // Try to parse as JSON if it's a string
        let data = response;
        if (typeof response === 'string') {
            data = JSON.parse(response);
        }
        
        // If JSON formatting is enabled, pretty print
        if (jsonFormatEnabled && typeof data === 'object') {
            return JSON.stringify(data, null, 2);
        }
        
        // Otherwise, use compact format
        return JSON.stringify(data);
    } catch (error) {
        // If not JSON, return as string
        return String(response);
    }
}

/**
 * Checks if JSON formatting is enabled
 * @returns {boolean} - Whether JSON formatting is enabled
 */
function isJsonFormatEnabledLocal() {
    return isJsonFormatEnabled();
}

/**
 * Adds tool calls indicator to an existing message
 * @param {HTMLElement} messageDiv - The message element
 * @param {number} toolCount - Number of tool calls
 * @param {Array} toolCalls - Array of tool call objects
 */
export function addToolCallsIndicatorToMessage(messageDiv, toolCount, toolCalls = []) {
    if (!toolCount || toolCount === 0) {
        return;
    }

    // Check if indicator already exists to prevent duplicates
    const existingIndicator = messageDiv.querySelector('.message-tools-indicator');
    if (existingIndicator) {
        Logger.info('Tool calls indicator already exists, skipping duplicate', { toolCount });
        return;
    }

    // Create the indicator
    const indicator = createToolCallsIndicator(toolCount, toolCalls);
    
    if (indicator) {
        // Append the indicator to the message div (positioned absolutely at bottom-right)
        messageDiv.appendChild(indicator);
    }
}

/**
 * Updates tool calls indicator with new data
 * @param {HTMLElement} messageDiv - The message element
 * @param {number} toolCount - Number of tool calls
 * @param {Array} toolCalls - Array of tool call objects
 */
export function updateToolCallsIndicator(messageDiv, toolCount, toolCalls = []) {
    // Remove existing indicator
    const existingIndicator = messageDiv.querySelector('.message-tools-indicator');
    if (existingIndicator) {
        existingIndicator.remove();
    }
    
    // Add new indicator
    addToolCallsIndicatorToMessage(messageDiv, toolCount, toolCalls);
}
