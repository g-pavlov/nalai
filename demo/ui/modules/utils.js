/**
 * Utilities Module
 * Contains utility functions and configurations
 */

export function configureMarked() {
    if (typeof marked === 'undefined') {
        throw new Error('Marked.js library not loaded');
    }

    marked.setOptions({
        breaks: true,
        gfm: true,
        sanitize: false,
        smartLists: true,
        smartypants: true
    });
}
