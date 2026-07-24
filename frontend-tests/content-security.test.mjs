import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

import { JSDOM } from 'jsdom';

const scripts = [
    'backend/static/vendor/marked.min.js',
    'backend/static/vendor/purify.min.js',
    'backend/static/content-security.js'
];

function createWindow() {
    const dom = new JSDOM('<!doctype html><body></body>', {
        runScripts: 'outside-only',
        url: 'https://chatraw.test/'
    });
    const context = dom.getInternalVMContext();
    for (const path of scripts) {
        vm.runInContext(fs.readFileSync(path, 'utf8'), context, {
            filename: path
        });
    }
    return dom.window;
}

test('untrusted Markdown keeps ordinary formatting', () => {
    const window = createWindow();
    const html = window.ChatRawContentSecurity.renderMarkdown(
        '# Title\n\n**bold** and [safe](https://example.com)'
    );
    assert.match(html, /<h1>Title<\/h1>/);
    assert.match(html, /<strong>bold<\/strong>/);
    assert.match(html, /href="https:\/\/example\.com"/);
});

test('untrusted Markdown removes executable HTML and protocols', () => {
    const window = createWindow();
    const html = window.ChatRawContentSecurity.renderMarkdown([
        '<script>window.pwned = true</script>',
        '<img src=x onerror="window.pwned=true">',
        '<svg onload="window.pwned=true"></svg>',
        '[bad](javascript:alert(1))',
        '<form action="/api/admin/users"><button>run</button></form>'
    ].join('\n'));
    assert.doesNotMatch(
        html,
        /<script|onerror|onload|(?:href|src)\s*=\s*["']?javascript:|<form|<button/i
    );
    assert.equal(window.pwned, undefined);
});

test('missing Markdown dependencies fail closed as escaped text', () => {
    const window = createWindow();
    delete window.marked;
    delete window.DOMPurify;
    const html = window.ChatRawContentSecurity.renderMarkdown(
        '<img src=x onerror=alert(1)>\nhello'
    );
    assert.equal(
        html,
        '&lt;img src=x onerror=alert(1)&gt;<br>hello'
    );
});
