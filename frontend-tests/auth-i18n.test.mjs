import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';

import { JSDOM } from 'jsdom';

const authScript = fs.readFileSync('backend/static/auth.js', 'utf8');
const authStyles = fs.readFileSync('backend/static/auth.css', 'utf8');

function response(payload, ok = true) {
    return {
        ok,
        async json() {
            return payload;
        }
    };
}

function createAuthWindow(page, language, fetchImpl, backgroundLoads = true) {
    const html = fs.readFileSync(`backend/static/${page}.html`, 'utf8');
    const dom = new JSDOM(html, {
        runScripts: 'outside-only',
        url: `https://chatraw.test/${page}`
    });
    if (language) dom.window.localStorage.setItem('justchat_lang', language);
    dom.window.fetch = fetchImpl;
    dom.window.setTimeout = () => 0;
    dom.window.Image = class {
        set src(_value) {
            Promise.resolve().then(() => {
                if (backgroundLoads) this.onload?.();
                else this.onerror?.(new Error('decode failed'));
            });
        }
    };
    vm.runInContext(authScript, dom.getInternalVMContext(), {
        filename: 'backend/static/auth.js'
    });
    return dom.window;
}

async function flushAsyncWork() {
    await new Promise(resolve => setImmediate(resolve));
}

test('login initializes from justchat_lang and localizes the complete page', async () => {
    const window = createAuthWindow(
        'login',
        'zh',
        async path => path === '/api/settings/logo'
            ? response({
                logo_data: 'data:image/png;base64,AA==',
                logo_text: '站务智枢',
                login_background_data: 'data:image/png;base64,Qkc='
            })
            : response({setup_required: false})
    );
    await flushAsyncWork();

    assert.equal(window.document.documentElement.lang, 'zh-CN');
    assert.equal(window.document.title, '登录 · ChatRaw Server');
    assert.equal(window.document.querySelector('h1').textContent, '继续你的工作');
    assert.equal(
        window.document.querySelector('label[for="username"]').textContent,
        '用户名'
    );
    assert.equal(
        window.document.querySelector('button[type="submit"]').textContent,
        '登录'
    );
    assert.equal(
        window.document.querySelector('.login-cancel').textContent,
        '取消'
    );
    assert.equal(
        window.document.querySelector('#public-logo-text').textContent,
        '站务智枢'
    );
    const logo = window.document.querySelector('#public-logo');
    logo.dispatchEvent(new window.Event('error'));
    assert.equal(logo.getAttribute('src'), '/brand-mark.svg');
    assert.equal(
        window.document.querySelector('.language-switch').ariaLabel,
        '语言'
    );
    const loginPage = window.document.querySelector('.login-page-shell');
    assert.equal(loginPage.classList.contains('has-custom-background'), true);
    assert.match(loginPage.style.backgroundImage, /data:image\/png;base64,Qkc=/);
    assert.equal(
        window.document.querySelector('.login-field').ariaLabel,
        '自定义登录页背景图'
    );
    assert.match(
        authStyles,
        /\.login-page-shell\.has-custom-background \.login-field-copy\s*\{[^}]*display:\s*none/s
    );
    assert.equal(
        window.document.querySelector('[data-language="zh"]').ariaPressed,
        'true'
    );
});

test('login keeps the bundled artwork and copy when custom decoding fails', async () => {
    const window = createAuthWindow(
        'login',
        'en',
        async path => path === '/api/settings/logo'
            ? response({
                logo_data: '',
                logo_text: 'ChatRaw',
                login_background_data: 'data:image/png;base64,broken'
            })
            : response({setup_required: false}),
        false
    );
    await flushAsyncWork();

    const loginPage = window.document.querySelector('.login-page-shell');
    assert.equal(loginPage.classList.contains('has-custom-background'), false);
    assert.equal(
        window.document.querySelector('.login-field').ariaLabel,
        'Warm gray abstract architectural landscape'
    );
    assert.equal(
        window.document.querySelector('.login-field-copy h2').textContent,
        'Put complex work in one place.'
    );
});

test('login actions share the main shell button hierarchy', () => {
    assert.match(authStyles, /body\[data-mode="login"\] \.shell\s*\{[^}]*width:\s*min\(100%, 392px\)/s);
    assert.match(authStyles, /body\[data-mode="login"\] \.shell\s*\{[^}]*background:\s*rgba\(255, 255, 255, \.52\)/s);
    assert.match(authStyles, /\.login-actions\s*\{[^}]*justify-content:\s*center/s);
    assert.match(authStyles, /\.login-actions button\s*\{[^}]*min-height:\s*44px/s);
    assert.match(authStyles, /\.login-actions button\s*\{[^}]*width:\s*min\(100%, 132px\)/s);
    assert.match(authStyles, /@media \(max-width:\s*380px\)\s*\{[^}]*\.login-actions button\s*\{[^}]*flex:\s*1 1 0/s);
    assert.match(authStyles, /\.login-actions button\s*\{[^}]*border-radius:\s*8px/s);
    assert.match(authStyles, /\.login-actions button\s*\{[^}]*font-weight:\s*550/s);
    assert.match(authStyles, /button\[type="submit"\]\s*\{[^}]*background:\s*#111/s);
    assert.match(authStyles, /\.login-cancel\s*\{[^}]*background:\s*transparent/s);
    assert.match(authStyles, /\.login-actions button:focus-visible\s*\{[^}]*outline:\s*2px solid #315f3a/s);
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
    assert.equal(window.document.querySelector('h1').textContent, 'Continue your work');
    assert.equal(
        window.document.querySelector('.intro').textContent,
        'Sign in with your platform account.'
    );
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
        if (path === '/api/settings/logo') {
            return response({logo_data: '', logo_text: 'ChatRaw'});
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

    assert.equal(requestCount, 3);
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
