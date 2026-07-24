(function installChatRawContentSecurity(global) {
    'use strict';

    const MARKDOWN_POLICY = Object.freeze({
        USE_PROFILES: { html: true },
        FORBID_TAGS: [
            'base',
            'button',
            'embed',
            'form',
            'iframe',
            'input',
            'link',
            'math',
            'meta',
            'object',
            'option',
            'script',
            'select',
            'style',
            'svg',
            'template',
            'textarea'
        ],
        FORBID_ATTR: ['style']
    });

    function escapedPlainText(text) {
        const fallback = global.document.createElement('div');
        fallback.textContent = text;
        return fallback.innerHTML.replace(/\n/g, '<br>');
    }

    function renderMarkdown(content) {
        const text = String(content || '');
        if (!text) return '';
        if (!global.marked || !global.DOMPurify) {
            return escapedPlainText(text);
        }
        return global.DOMPurify.sanitize(
            global.marked.parse(text),
            MARKDOWN_POLICY
        );
    }

    global.ChatRawContentSecurity = Object.freeze({
        renderMarkdown
    });
})(window);
