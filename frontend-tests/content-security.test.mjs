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
    assert.doesNotMatch(html, /markdown-table-scroll/);
});

test('Markdown tables are wrapped in a keyboard-focusable horizontal scroller', () => {
    const window = createWindow();
    window.document.documentElement.lang = 'en';
    const markdown = [
        '| 序号 | 交易时间 | 车牌号 | 车牌颜色 | 车型 | 车种 | 车道 | 车道类型 |',
        '| --- | --- | --- | --- | --- | --- | --- | --- |',
        '| 1 | 23:59:15 | 鲁S3609W | 蓝 | 客一 | 普通车 | 82 | ETC入口 |'
    ].join('\n');
    const html = window.ChatRawContentSecurity.renderMarkdown(
        markdown,
        'zh-CN'
    );

    const surface = window.document.createElement('div');
    surface.innerHTML = html;
    const scroller = surface.querySelector('.markdown-table-scroll');

    assert.ok(scroller);
    assert.equal(scroller.getAttribute('tabindex'), '0');
    assert.equal(scroller.getAttribute('role'), 'region');
    assert.equal(scroller.getAttribute('aria-label'), '可横向滚动的表格');
    assert.ok(scroller.querySelector(':scope > table'));

    surface.innerHTML = window.ChatRawContentSecurity.renderMarkdown(
        markdown,
        'en'
    );
    assert.equal(
        surface.querySelector('.markdown-table-scroll')
            .getAttribute('aria-label'),
        'Scrollable table'
    );
});

test('table wrapping happens after sanitization without restoring unsafe markup', () => {
    const window = createWindow();
    const html = window.ChatRawContentSecurity.renderMarkdown([
        '<table onclick="window.pwned=true">',
        '<tr><td><img src="x" onerror="window.pwned=true">safe</td></tr>',
        '<script>window.pwned=true</script>',
        '</table>'
    ].join(''), 'en');

    const surface = window.document.createElement('div');
    surface.innerHTML = html;
    const scroller = surface.querySelector('.markdown-table-scroll');

    assert.ok(scroller);
    assert.equal(scroller.querySelector('td')?.textContent, 'safe');
    assert.doesNotMatch(html, /onclick|onerror|<script/i);
    assert.equal(window.pwned, undefined);
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
