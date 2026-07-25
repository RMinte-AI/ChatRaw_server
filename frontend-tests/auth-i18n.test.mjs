import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

import { JSDOM } from 'jsdom';

const authScript = fs.readFileSync('backend/static/auth.js', 'utf8');

function response(payload, ok = true) {
    return {
        ok,
        async json() {
            return payload;
        }
    };
}

function createAuthWindow(page, language, fetchImpl) {
    const html = fs.readFileSync(`backend/static/${page}.html`, 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'outside-only',
        url: `https://chatraw.test/${page}`
    });
    if (language) dom.window.localStorage.setItem('justchat_lang', language);
    dom.window.fetch = fetchImpl;
    dom.window.setTimeout = () => 0;
    vm.runInContext(authScript, dom.getInternalVMContext(), {
        filename: 'backend/static/auth.js'
    });
    return dom.window;
}

async function flushAsyncWork() {
    await new Promise(resolve => setImmediate(resolve));
}

test('login initializes from justchat_lang and localizes the complete page', () => {
    const window = createAuthWindow(
        'login',
        'zh',
        async () => response({setup_required: false})
    );

    assert.equal(window.document.documentElement.lang, 'zh-CN');
    assert.equal(window.document.title, '登录 · ChatRaw Server');
    assert.equal(window.document.querySelector('h1').textContent, '欢迎回来。');
    assert.equal(
        window.document.querySelector('label[for="username"]').textContent,
        '用户名'
    );
    assert.equal(
        window.document.querySelector('button[type="submit"]').textContent,
        '登录'
    );
    assert.equal(
        window.document.querySelector('.language-switch').ariaLabel,
        '语言'
    );
    assert.equal(
        window.document.querySelector('[data-language="zh"]').ariaPressed,
        'true'
    );
});

test('language switch updates text, document metadata, and storage', () => {
    const window = createAuthWindow(
        'login',
        'zh',
        async () => response({setup_required: false})
    );

    window.document.querySelector('[data-language="en"]').click();

    assert.equal(window.localStorage.getItem('justchat_lang'), 'en');
    assert.equal(window.document.documentElement.lang, 'en');
    assert.equal(window.document.title, 'Sign in · ChatRaw Server');
    assert.equal(window.document.querySelector('h1').textContent, 'Welcome back.');
    assert.equal(
        window.document.querySelector('[data-language="en"]').ariaPressed,
        'true'
    );
});

test('login localizes a known authentication error', async () => {
    let requestCount = 0;
    const window = createAuthWindow('login', 'zh', async path => {
        requestCount += 1;
        if (path === '/api/setup/status') {
            return response({setup_required: false});
        }
        return response({
            detail: 'opaque server fallback',
            code: 'invalid_credentials'
        }, false);
    });

    window.document.querySelector('#username').value = 'member';
    window.document.querySelector('#password').value = 'wrong-password';
    window.document.querySelector('form').dispatchEvent(
        new window.Event('submit', {bubbles: true, cancelable: true})
    );
    await flushAsyncWork();

    assert.equal(requestCount, 2);
    assert.equal(
        window.document.querySelector('.message').textContent,
        '用户名或密码错误'
    );
    assert.equal(
        window.document.querySelector('button[type="submit"]').disabled,
        false
    );
});

test('setup success message follows the selected language', async () => {
    const window = createAuthWindow('setup', 'zh', async path => {
        if (path === '/api/setup/status') {
            return response({setup_required: true});
        }
        return response({success: true});
    });

    window.document.querySelector('form').dispatchEvent(
        new window.Event('submit', {bubbles: true, cancelable: true})
    );
    await flushAsyncWork();

    assert.equal(window.document.title, '初始化 · ChatRaw Server');
    assert.equal(
        window.document.querySelector('.message').textContent,
        '管理员已创建，请继续登录。'
    );
    assert.equal(
        window.document.querySelector('.message').classList.contains('success'),
        true
    );
});

test('unknown response details fail closed to a localized generic message', async () => {
    const window = createAuthWindow('login', 'zh', async path => {
        if (path === '/api/setup/status') {
            return response({setup_required: false});
        }
        return response({detail: 'internal upstream detail'}, false);
    });

    window.document.querySelector('form').dispatchEvent(
        new window.Event('submit', {bubbles: true, cancelable: true})
    );
    await flushAsyncWork();

    assert.equal(
        window.document.querySelector('.message').textContent,
        '请求失败'
    );
    assert.doesNotMatch(
        window.document.querySelector('.message').textContent,
        /internal upstream detail/
    );
});
