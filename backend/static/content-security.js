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

    function wrapMarkdownTables(html, language) {
        const surface = global.document.createElement('div');
        surface.innerHTML = html;
        const isChinese = String(
            language || global.document.documentElement.lang || ''
        )
            .toLowerCase()
            .startsWith('zh');
        for (const table of surface.querySelectorAll('table')) {
            const scroller = global.document.createElement('div');
            scroller.className = 'markdown-table-scroll';
            scroller.tabIndex = 0;
            scroller.setAttribute('role', 'region');
            scroller.setAttribute(
                'aria-label',
                isChinese ? '可横向滚动的表格' : 'Scrollable table'
            );
            table.replaceWith(scroller);
            scroller.append(table);
        }
        return surface.innerHTML;
    }

    function renderMarkdown(
        content,
        language = global.document.documentElement.lang
    ) {
        const text = String(content || '');
        if (!text) return '';
        if (!global.marked || !global.DOMPurify) {
            return escapedPlainText(text);
        }
        return wrapMarkdownTables(
            global.DOMPurify.sanitize(
                global.marked.parse(text),
                MARKDOWN_POLICY
            ),
            language
        );
    }

    global.ChatRawContentSecurity = Object.freeze({
        renderMarkdown
    });
})(window);
