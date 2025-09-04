/**
 * Conversations Manager Module
 * Handles conversations list display and management
 */

import { DOM } from './dom.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';
import { NetworkManager } from './network.js';
import { buildApiUrl, API_CONFIG } from './config.js';
import { getRequestHeaders } from './settings.js';
import { loadConversation } from './conversations.js';

let conversations = [];
let isLoading = false;

export async function showConversationsList() {
    try {
        Logger.info('Showing conversations list');
        
        // Show the panel
        DOM.conversationsPanel.classList.add('show');
        
        // Load conversations
        await loadConversations();
        
    } catch (error) {
        Logger.error('Failed to show conversations list', { error });
        ErrorHandler.showUserError('Failed to show conversations list');
    }
}

export function hideConversationsList() {
    Logger.info('Hiding conversations list');
    DOM.conversationsPanel.classList.remove('show');
}

export async function refreshConversationsList() {
    try {
        Logger.info('Refreshing conversations list');
        await loadConversations();
    } catch (error) {
        Logger.error('Failed to refresh conversations list', { error });
        ErrorHandler.showUserError('Failed to refresh conversations list');
    }
}

async function loadConversations() {
    if (isLoading) {
        Logger.warn('Conversations already loading, skipping request');
        return;
    }
    
    try {
        isLoading = true;
        showLoadingState();
        
        // Check network status
        if (!NetworkManager.isOnline()) {
            throw new Error('No internet connection. Please check your network and try again.');
        }
        
        // Build the API URL
        const url = buildApiUrl(API_CONFIG.URL_TEMPLATES.CONVERSATIONS);
        const headers = getRequestHeaders(false, false); // No streaming for listing
        
        Logger.info('Loading conversations from API', { url });
        
        // Make the API request
        const response = await NetworkManager.fetchWithRetry(url, {
            method: 'GET',
            headers
        });
        
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorBody = await response.text();
                if (errorBody) {
                    const errorJson = JSON.parse(errorBody);
                    if (errorJson.detail) {
                        errorMessage += ` - ${errorJson.detail}`;
                    }
                }
            } catch (parseError) {
                Logger.warn('Could not parse error response', { parseError });
            }
            
            const error = new Error(errorMessage);
            error.status = response.status;
            throw error;
        }
        
        const data = await response.json();
        conversations = data.conversations || [];
        
        Logger.info('Conversations loaded successfully', { count: conversations.length });
        
        // Display conversations
        displayConversations();
        
    } catch (error) {
        Logger.error('Failed to load conversations', { error });
        showErrorState(error.message);
    } finally {
        isLoading = false;
    }
}

function showLoadingState() {
    DOM.conversationsLoading.style.display = 'block';
    DOM.conversationsList.style.display = 'none';
    DOM.conversationsEmpty.style.display = 'none';
    DOM.conversationsError.style.display = 'none';
}

function showErrorState(errorMessage) {
    DOM.conversationsLoading.style.display = 'none';
    DOM.conversationsList.style.display = 'none';
    DOM.conversationsEmpty.style.display = 'none';
    DOM.conversationsError.style.display = 'block';
    
    const errorElement = DOM.conversationsError.querySelector('p');
    if (errorElement) {
        errorElement.textContent = `Failed to load conversations: ${errorMessage}`;
    }
}

function displayConversations() {
    DOM.conversationsLoading.style.display = 'none';
    DOM.conversationsError.style.display = 'none';
    
    if (conversations.length === 0) {
        DOM.conversationsList.style.display = 'none';
        DOM.conversationsEmpty.style.display = 'block';
        return;
    }
    
    DOM.conversationsList.style.display = 'flex';
    DOM.conversationsEmpty.style.display = 'none';
    
    // Clear existing list
    DOM.conversationsList.innerHTML = '';
    
    // Sort conversations by last updated (newest first)
    const sortedConversations = [...conversations].sort((a, b) => {
        const dateA = a.last_updated ? new Date(a.last_updated) : new Date(a.created_at || 0);
        const dateB = b.last_updated ? new Date(b.last_updated) : new Date(b.created_at || 0);
        return dateB - dateA;
    });
    
    // Create conversation items
    sortedConversations.forEach(conversation => {
        const conversationElement = createConversationElement(conversation);
        DOM.conversationsList.appendChild(conversationElement);
    });
}

function createConversationElement(conversation) {
    const element = document.createElement('div');
    element.className = 'conversation-item';
    
    // Format dates
    const createdDate = conversation.created_at ? formatDate(conversation.created_at) : 'Unknown';
    const lastAccessedDate = conversation.last_updated ? formatDate(conversation.last_updated) : createdDate;
    
    // Get title from metadata or use conversation ID
    const title = conversation.metadata?.title || `Conversation ${conversation.conversation_id.slice(0, 8)}`;
    
    // Create preview text
    const preview = conversation.preview || 'No preview available';
    
    element.innerHTML = `
        <div class="conversation-item-content" onclick="window.selectConversationFromElement('${conversation.conversation_id}')">
            <p class="conversation-item-preview">${escapeHtml(preview)}</p>
            <span class="conversation-item-date" title="Last accessed">${lastAccessedDate}</span>
        </div>
        <div class="conversation-item-actions">
            <button class="conversation-delete-btn" onclick="window.deleteConversationFromElement('${conversation.conversation_id}', '${escapeHtml(title)}')" title="Delete conversation">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3,6 5,6 21,6"></polyline>
                    <path d="M19,6v14a2,2 0 0,1 -2,2H7a2,2 0 0,1 -2,-2V6m3,0V4a2,2 0 0,1 2,-2h4a2,2 0 0,1 2,2v2"></path>
                    <line x1="10" y1="11" x2="10" y2="17"></line>
                    <line x1="14" y1="11" x2="14" y2="17"></line>
                </svg>
            </button>
        </div>
    `;
    
    return element;
}

function createMetadataTags(metadata) {
    if (!metadata || Object.keys(metadata).length === 0) {
        return '';
    }
    
    const tags = [];
    
    // Add status if available
    if (metadata.status) {
        tags.push(`<span class="conversation-item-tag">${escapeHtml(metadata.status)}</span>`);
    }
    
    // Add other metadata as tags (excluding title and status)
    Object.entries(metadata).forEach(([key, value]) => {
        if (key !== 'title' && key !== 'status' && value) {
            if (typeof value === 'string') {
                tags.push(`<span class="conversation-item-tag">${escapeHtml(value)}</span>`);
            } else if (Array.isArray(value)) {
                value.forEach(item => {
                    if (item) {
                        tags.push(`<span class="conversation-item-tag">${escapeHtml(String(item))}</span>`);
                    }
                });
            }
        }
    });
    
    if (tags.length === 0) {
        return '';
    }
    
    return `<div class="conversation-item-metadata">${tags.join('')}</div>`;
}

async function selectConversation(conversation) {
    try {
        Logger.info('Selecting conversation', { conversationId: conversation.conversation_id });
        
        // Hide the conversations panel
        hideConversationsList();
        
        // Load the selected conversation
        await loadConversation(conversation.conversation_id, true);
        
    } catch (error) {
        Logger.error('Failed to select conversation', { conversationId: conversation.conversation_id, error });
        ErrorHandler.showUserError(`Failed to load conversation: ${error.message}`);
    }
}

async function deleteConversation(conversationId, conversationTitle) {
    try {
        Logger.info('Deleting conversation', { conversationId, conversationTitle });
        
        // Show confirmation dialog
        const confirmed = confirm(`Are you sure you want to delete "${conversationTitle}"?\n\nThis action cannot be undone.`);
        if (!confirmed) {
            Logger.info('Conversation deletion cancelled by user');
            return;
        }
        
        // Check network status
        if (!NetworkManager.isOnline()) {
            throw new Error('No internet connection. Please check your network and try again.');
        }
        
        // Build the API URL
        const url = buildApiUrl(API_CONFIG.URL_TEMPLATES.CONVERSATION, { conversation_id: conversationId });
        const headers = getRequestHeaders(false, false); // No streaming for deletion
        
        Logger.info('Deleting conversation from API', { url });
        
        // Make the API request
        const response = await NetworkManager.fetchWithRetry(url, {
            method: 'DELETE',
            headers
        });
        
        if (!response.ok) {
            let errorMessage = `HTTP ${response.status}: ${response.statusText}`;
            try {
                const errorBody = await response.text();
                if (errorBody) {
                    const errorJson = JSON.parse(errorBody);
                    if (errorJson.detail) {
                        errorMessage += ` - ${errorJson.detail}`;
                    }
                }
            } catch (parseError) {
                Logger.warn('Could not parse error response', { parseError });
            }
            
            const error = new Error(errorMessage);
            error.status = response.status;
            throw error;
        }
        
        Logger.info('Conversation deleted successfully', { conversationId });
        
        // Show success message
        ErrorHandler.showUserSuccess(`Conversation "${conversationTitle}" deleted successfully`);
        
        // Refresh the conversations list
        await refreshConversationsList();
        
    } catch (error) {
        Logger.error('Failed to delete conversation', { conversationId, error });
        ErrorHandler.showUserError(`Failed to delete conversation: ${error.message}`);
    }
}

// Global functions for onclick handlers
window.selectConversationFromElement = async function(conversationId) {
    const conversation = conversations.find(c => c.conversation_id === conversationId);
    if (conversation) {
        await selectConversation(conversation);
    }
};

window.deleteConversationFromElement = async function(conversationId, conversationTitle) {
    // Prevent event bubbling to avoid triggering the select function
    event.stopPropagation();
    await deleteConversation(conversationId, conversationTitle);
};

function formatDate(dateString) {
    try {
        const date = new Date(dateString);
        const now = new Date();
        const diffInHours = (now - date) / (1000 * 60 * 60);
        
        if (diffInHours < 24) {
            return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        } else if (diffInHours < 168) { // 7 days
            return date.toLocaleDateString([], { weekday: 'short', hour: '2-digit', minute: '2-digit' });
        } else {
            return date.toLocaleDateString([], { month: 'short', day: 'numeric', year: 'numeric' });
        }
    } catch (error) {
        Logger.warn('Failed to format date', { dateString, error });
        return 'Unknown';
    }
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}
