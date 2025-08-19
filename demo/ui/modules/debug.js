/**
 * Debug Module
 * Handles agent progress visualization and debug features
 */

import { Logger } from './logger.js';

// Debug state management
let debugState = {
    isEnabled: false,
    currentNode: null,
    nodeLogs: [],
    toolCalls: [],
    finalMessage: null,
    isComplete: false
};

// Node mapping for human-readable names (current/active status)
const NODE_DISPLAY_NAMES = {
    'call_model': 'AI processing',
    'call_api': 'Tool calling',
    'check_cache': 'Checking cache',
    'load_api_summaries': 'Loading API summaries',
    'load_api_specs': 'Loading API specifications',
    'select_relevant_apis': 'AI selecting APIs'
};

// Node mapping for completed status (past tense for update events)
const NODE_COMPLETED_NAMES = {
    'call_model': 'AI processed',
    'call_api': 'Tool called',
    'check_cache': 'Cache checked',
    'load_api_summaries': 'API summaries loaded',
    'load_api_specs': 'API specifications loaded',
    'select_relevant_apis': 'APIs selected'
};

export function initializeDebug() {
    // Load debug state from localStorage
    const savedDebugState = localStorage.getItem('nalai_debug_enabled');
    debugState.isEnabled = savedDebugState === 'true';
    
    // Update UI to reflect current state
    updateDebugToggle();
    
    Logger.info('Debug module initialized', { isEnabled: debugState.isEnabled });
}

export function toggleDebug() {
    debugState.isEnabled = !debugState.isEnabled;
    
    // Save to localStorage
    localStorage.setItem('nalai_debug_enabled', debugState.isEnabled.toString());
    
    // Update UI
    updateDebugToggle();
    
    Logger.info('Debug toggled', { isEnabled: debugState.isEnabled });
}

export function isDebugEnabled() {
    return debugState.isEnabled;
}

export function resetDebugState() {
    debugState = {
        isEnabled: debugState.isEnabled, // Preserve the enabled state
        currentNode: null,
        nodeLogs: [],
        toolCalls: [],
        finalMessage: null,
        isComplete: false
    };
    
    Logger.info('Debug state reset');
}

export function addNodeLog(nodeName, updateValue) {
    if (!debugState.isEnabled) return;
    
    const nodeLog = {
        node: nodeName,
        displayName: NODE_COMPLETED_NAMES[nodeName] || NODE_DISPLAY_NAMES[nodeName] || nodeName,
        status: 'completed',
        timestamp: new Date().toISOString(),
        output: updateValue
    };
    
    debugState.nodeLogs.push(nodeLog);
    debugState.currentNode = nodeName;
    
    Logger.info('Node log added', { nodeName, nodeLog });
}

export function addToolCall(toolName, content) {
    if (!debugState.isEnabled) return;
    
    const toolCall = {
        name: toolName || 'Unknown tool',
        content: content,
        timestamp: new Date().toISOString()
    };
    
    debugState.toolCalls.push(toolCall);
    
    Logger.info('Tool call added', { toolCall });
}

export function setFinalMessage(content) {
    if (!debugState.isEnabled) return;
    
    debugState.finalMessage = content;
    debugState.isComplete = true;
    
    Logger.info('Final message set', { length: content?.length || 0 });
}

export function updateProgressDisplay(assistantMessageDiv) {
    if (!debugState.isEnabled) return;
    
    // Create or update the progress container
    let progressContainer = assistantMessageDiv.querySelector('.streaming-progress');
    if (!progressContainer) {
        progressContainer = createProgressContainer(assistantMessageDiv);
    }
    
    // Update the progress content
    const progressContent = progressContainer.querySelector('.progress-content');
    progressContent.innerHTML = '';
    
    debugState.nodeLogs.forEach((log, index) => {
        const nodeElement = createNodeElement(log, index);
        progressContent.appendChild(nodeElement);
    });
    
    // Scroll to bottom
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

export function updateFinalMessageContent(assistantMessageDiv, content) {
    if (!debugState.isEnabled) return;
    
    // Create or update the final message container
    let finalMessageContainer = assistantMessageDiv.querySelector('.final-message');
    if (!finalMessageContainer) {
        finalMessageContainer = createFinalMessageContainer(assistantMessageDiv);
    }
    
    // Update the content
    const messageContent = finalMessageContainer.querySelector('.message-content');
    try {
        messageContent.innerHTML = marked.parse(content);
    } catch (error) {
        messageContent.textContent = content;
    }
    
    // Scroll to bottom
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

export function createFinalUI(assistantMessageDiv) {
    if (!debugState.isEnabled) return;
    
    // Clear the current content
    assistantMessageDiv.innerHTML = '';
    
    // Create the log panel (collapsed by default)
    if (debugState.nodeLogs.length > 0 || debugState.toolCalls.length > 0) {
        const logPanel = createLogPanel();
        assistantMessageDiv.appendChild(logPanel);
    }
    
    // Create the final AI message
    if (debugState.finalMessage) {
        const finalMessageDiv = document.createElement('div');
        finalMessageDiv.className = 'ai-message-final';
        finalMessageDiv.innerHTML = `
            <div class="message-header">
                <span class="message-icon">AI</span>
                <span class="message-title">Response</span>
            </div>
            <div class="message-content"></div>
        `;
        
        const messageContent = finalMessageDiv.querySelector('.message-content');
        try {
            messageContent.innerHTML = marked.parse(debugState.finalMessage);
        } catch (error) {
            messageContent.textContent = debugState.finalMessage;
        }
        
        assistantMessageDiv.appendChild(finalMessageDiv);
    }
    
    // Scroll to bottom
    const chatContainer = document.getElementById('chatContainer');
    if (chatContainer) {
        chatContainer.scrollTop = chatContainer.scrollHeight;
    }
}

function createProgressContainer(assistantMessageDiv) {
    const progressContainer = document.createElement('div');
    progressContainer.className = 'streaming-progress';
    progressContainer.innerHTML = `
        <div class="progress-header">
            <span class="progress-title">Agent Progress</span>
            <span class="progress-status">Processing...</span>
        </div>
        <div class="progress-content"></div>
    `;
    
    assistantMessageDiv.appendChild(progressContainer);
    return progressContainer;
}

function createNodeElement(log, index) {
    const nodeElement = document.createElement('div');
    nodeElement.className = 'node-item';
    nodeElement.innerHTML = `
        <div class="node-header">
            <span class="node-icon">✓</span>
            <span class="node-name">${log.displayName}</span>
            <span class="node-time">${formatTime(log.timestamp)}</span>
        </div>
        ${log.output ? `<div class="node-output">${formatNodeOutput(log.output)}</div>` : ''}
    `;
    
    return nodeElement;
}

function createFinalMessageContainer(assistantMessageDiv) {
    const finalMessageContainer = document.createElement('div');
    finalMessageContainer.className = 'final-message';
    finalMessageContainer.innerHTML = `
        <div class="message-header">
            <span class="message-icon">AI</span>
            <span class="message-title">Response</span>
        </div>
        <div class="message-content"></div>
    `;
    
    assistantMessageDiv.appendChild(finalMessageContainer);
    return finalMessageContainer;
}

function createLogPanel() {
    const logPanel = document.createElement('div');
    logPanel.className = 'log-panel collapsed';
    logPanel.innerHTML = `
        <div class="log-header" onclick="toggleLogPanel(this)">
            <span class="log-icon">Log</span>
            <span class="log-title">Execution Details</span>
            <span class="log-toggle">▼</span>
        </div>
        <div class="log-content">
            ${createLogContent()}
        </div>
    `;
    
    return logPanel;
}

function createLogContent() {
    let content = '';
    
    // Add node logs
    if (debugState.nodeLogs.length > 0) {
        content += '<div class="log-section"><h4>Processing Steps</h4>';
        debugState.nodeLogs.forEach((log, index) => {
            content += `
                <div class="log-item">
                    <div class="log-item-header">
                        <span class="log-item-icon">✓</span>
                        <span class="log-item-name">${log.displayName}</span>
                        <span class="log-item-time">${formatTime(log.timestamp)}</span>
                    </div>
                    ${log.output ? `<div class="log-item-output">${formatNodeOutput(log.output)}</div>` : ''}
                </div>
            `;
        });
        content += '</div>';
    }
    
    // Add tool calls
    if (debugState.toolCalls.length > 0) {
        content += '<div class="log-section"><h4>Tool Calls</h4>';
        debugState.toolCalls.forEach((tool, index) => {
            content += `
                <div class="log-item">
                    <div class="log-item-header">
                        <span class="log-item-icon">⚙</span>
                        <span class="log-item-name">${tool.name}</span>
                        <span class="log-item-time">${formatTime(tool.timestamp)}</span>
                    </div>
                    <div class="log-item-output">${tool.content}</div>
                </div>
            `;
        });
        content += '</div>';
    }
    
    return content;
}

function formatTime(timestamp) {
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
}

function formatNodeOutput(output) {
    if (typeof output === 'string') {
        return output;
    } else if (typeof output === 'object') {
        return JSON.stringify(output, null, 2);
    }
    return String(output);
}

function updateDebugToggle() {
    const debugToggle = document.getElementById('debugToggle');
    const debugStatus = document.getElementById('debugStatus');
    
    if (debugToggle) {
        debugToggle.checked = debugState.isEnabled;
    }
    
    if (debugStatus) {
        debugStatus.textContent = debugState.isEnabled ? 'ON' : 'OFF';
    }
}

// Global function for log panel toggle
window.toggleLogPanel = function(header) {
    const panel = header.parentElement;
    const content = panel.querySelector('.log-content');
    const toggle = header.querySelector('.log-toggle');
    
    if (panel.classList.contains('collapsed')) {
        panel.classList.remove('collapsed');
        panel.classList.add('expanded');
        content.style.display = 'block';
        toggle.textContent = '▲';
    } else {
        panel.classList.remove('expanded');
        panel.classList.add('collapsed');
        content.style.display = 'none';
        toggle.textContent = '▼';
    }
};
