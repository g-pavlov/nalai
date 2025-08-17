/**
 * Main Application Module
 * Initializes the application and provides global functions
 */

import { configureMarked } from './utils.js';
import { initializeDOMElements } from './dom.js';
import { NetworkManager } from './network.js';
import { loadSavedState } from './state.js';
import { showWelcomeMessage } from './messages.js';
import { Logger } from './logger.js';
import { ErrorHandler } from './errorHandler.js';

// Import other modules as needed
import { setupEventListeners, handleConnectionStatusChange, setSendMessageFunction } from './events.js';
import { startNewConversation } from './messages.js';
import { toggleSettings } from './settings.js';
import { sendMessage } from './api.js';
import { loadConversation } from './conversations.js';
import { handleInterrupt } from './interrupts.js';
import { showConversationsList, hideConversationsList, refreshConversationsList } from './conversationsManager.js';

export async function initializeApp() {
    try {
        Logger.info('Initializing nalAI Chat Interface');
        
        // Initialize DOM elements
        initializeDOMElements();
        
        // Configure marked.js
        configureMarked();
        
        // Setup event listeners
        setupEventListeners();
        
        // Set the sendMessage function in the events module
        setSendMessageFunction(sendMessage);
        
        // Setup network status monitoring
        NetworkManager.addOnlineStatusListener(handleConnectionStatusChange);
        
        // Load saved state and show welcome message if needed
        const loadedSuccessfully = await loadSavedState();
        if (!loadedSuccessfully) {
            showWelcomeMessage();
        }
        
        Logger.info('App initialization completed successfully');
        
    } catch (error) {
        ErrorHandler.handleError(error, 'App initialization');
        // Show welcome message as fallback if initialization fails
        showWelcomeMessage();
    }
}

// Global functions for HTML onclick handlers
export { sendMessage, startNewConversation, loadConversation, handleInterrupt, toggleSettings, showConversationsList, hideConversationsList, refreshConversationsList };


