/**
 * Utilities Module
 * Contains utility functions and configurations
 */

export function configureMarked() {
    if (typeof marked === 'undefined') {
        throw new Error('Marked.js library not loaded');
    }

    // Custom renderer to wrap tables in scrollable containers
    const renderer = new marked.Renderer();
    
    // Wrap tables in a div with table-wrapper class for horizontal scrolling
    renderer.table = function(header, body) {
        return `<div class="table-wrapper"><table><thead>${header}</thead><tbody>${body}</tbody></table></div>`;
    };
    
    // Ensure table headers and cells maintain structure
    renderer.tablerow = function(content) {
        return `<tr>${content}</tr>`;
    };
    
    renderer.tablecell = function(content, flags) {
        const tag = flags.header ? 'th' : 'td';
        return `<${tag}>${content}</${tag}>`;
    };

    marked.setOptions({
        breaks: true,
        gfm: true,
        sanitize: false,
        smartLists: true,
        smartypants: true,
        renderer: renderer
    });
}
