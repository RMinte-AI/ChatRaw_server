(function () {
    'use strict';

    const languageStorageKey = 'justchat_lang';
    const translations = {
        en: {
            languageSelector: 'Language',
            loginTitle: 'Sign in · ChatRaw Server',
            loginHeading: 'Continue your work',
            loginIntro: 'Sign in with your platform account.',
            username: 'Username',
            password: 'Password',
            signIn: 'Sign in',
            cancel: 'Cancel',
            welcomeBack: 'Welcome back',
            sharedWorkspace: 'Shared workspace',
            loginArtworkLabel: 'Warm gray abstract architectural landscape',
            loginCustomBackgroundLabel: 'Custom login page background',
            loginArtworkEyebrow: 'ChatRaw / Shared Intelligence',
            loginArtworkHeading: 'Put complex work in one place.',
            loginArtworkCopy: 'Conversations, knowledge and business modules work together in one clear workspace.',
            setupTitle: 'Set up · ChatRaw Server',
            setupEyebrow: 'First-run setup',
            setupHeading: 'Create the administrator.',
            setupIntro: 'Use the one-time token stored in the deployment secret file. It becomes permanently invalid after setup.',
            setupToken: 'Setup token',
            administratorUsername: 'Administrator username',
            createAdministrator: 'Create administrator',
            administratorCreated: 'Administrator created. Continue to sign in.',
            requestFailed: 'Request failed',
            invalidRequest: 'Invalid request',
            setupUnavailable: 'Setup is unavailable',
            usernameInUse: 'Username is already in use',
            invalidCredentials: 'Invalid username or password',
            usernameMustBeString: 'Username must be a string',
            usernameLength: 'Username must be {min}-{max} characters',
            usernameUnsupported: 'Username contains unsupported characters',
            passwordLength: 'Password must be at least {min} characters',
            passwordTooLong: 'Password is too long'
        },
        zh: {
            languageSelector: '语言',
            loginTitle: '登录 · ChatRaw Server',
            loginHeading: '继续你的工作',
            loginIntro: '使用平台账户登录。',
            username: '用户名',
            password: '密码',
            signIn: '登录',
            cancel: '取消',
            welcomeBack: '欢迎回来',
            sharedWorkspace: '多人共享工作空间',
            loginArtworkLabel: '暖灰色抽象建筑景观',
            loginCustomBackgroundLabel: '自定义登录页背景图',
            loginArtworkEyebrow: 'ChatRaw / 共享智能',
            loginArtworkHeading: '把复杂工作，放进一个入口。',
            loginArtworkCopy: '对话、知识与业务模块，在同一个清晰的工作空间中协作。',
            setupTitle: '初始化 · ChatRaw Server',
            setupEyebrow: '首次运行设置',
            setupHeading: '创建管理员。',
            setupIntro: '使用部署密钥文件中保存的一次性令牌。完成初始化后，该令牌将永久失效。',
            setupToken: '初始化令牌',
            administratorUsername: '管理员用户名',
            createAdministrator: '创建管理员',
            administratorCreated: '管理员已创建，请继续登录。',
            requestFailed: '请求失败',
            invalidRequest: '请求无效',
            setupUnavailable: '初始化已不可用',
            usernameInUse: '用户名已被使用',
            invalidCredentials: '用户名或密码错误',
            usernameMustBeString: '用户名必须是字符串',
            usernameLength: '用户名长度必须为 {min}-{max} 个字符',
            usernameUnsupported: '用户名包含不支持的字符',
            passwordLength: '密码至少需要 {min} 个字符',
            passwordTooLong: '密码过长'
        }
    };

    const mode = document.body.dataset.mode;
    const form = document.querySelector('form');
    const message = document.querySelector('.message');
    const submitButton = document.querySelector('button[type="submit"]');
    let language = readLanguage();
    let messageState = null;

    function readLanguage() {
        try {
            const stored = localStorage.getItem(languageStorageKey);
            return stored === 'zh' ? 'zh' : 'en';
        } catch (_error) {
            return 'en';
        }
    }

    function text(key, replacements = {}) {
        let value = translations[language][key] || translations.en[key] || key;
        for (const [name, replacement] of Object.entries(replacements)) {
            value = value.replace(`{${name}}`, String(replacement));
        }
        return value;
    }

    function localizeError(code, detail) {
        const normalized = typeof detail === 'string' ? detail.trim() : '';
        const codes = {
            invalid_request: 'invalidRequest',
            setup_unavailable: 'setupUnavailable',
            username_in_use: 'usernameInUse',
            invalid_credentials: 'invalidCredentials',
            invalid_username_type: 'usernameMustBeString',
            invalid_username_characters: 'usernameUnsupported',
            invalid_password_too_long: 'passwordTooLong'
        };
        if (codes[code]) return text(codes[code]);

        const exact = {
            'Invalid request': 'invalidRequest',
            'setup is unavailable': 'setupUnavailable',
            'username is already in use': 'usernameInUse',
            'invalid username or password': 'invalidCredentials',
            'username must be a string': 'usernameMustBeString',
            'username contains unsupported characters': 'usernameUnsupported',
            'password is too long': 'passwordTooLong'
        };
        if (exact[normalized]) return text(exact[normalized]);

        let match = normalized.match(/^username must be (\d+)-(\d+) characters$/);
        if (match) {
            return text('usernameLength', {min: match[1], max: match[2]});
        }
        match = normalized.match(/^password must be at least (\d+) characters$/);
        if (match) return text('passwordLength', {min: match[1]});
        return text('requestFailed');
    }

    function renderMessage() {
        if (!messageState) {
            message.textContent = '';
            message.classList.remove('success');
            return;
        }
        message.textContent = messageState.key
            ? text(messageState.key)
            : localizeError(messageState.code, messageState.detail);
        message.classList.toggle('success', messageState.success);
    }

    function showMessage(state = null) {
        messageState = state;
        renderMessage();
    }

    function applyLanguage(nextLanguage, persist = false) {
        language = nextLanguage === 'zh' ? 'zh' : 'en';
        if (persist) {
            try {
                localStorage.setItem(languageStorageKey, language);
            } catch (_error) {}
        }
        document.documentElement.lang = language === 'zh' ? 'zh-CN' : 'en';
        for (const element of document.querySelectorAll('[data-i18n]')) {
            element.textContent = text(element.dataset.i18n);
        }
        for (const element of document.querySelectorAll('[data-i18n-aria-label]')) {
            element.setAttribute(
                'aria-label',
                text(element.dataset.i18nAriaLabel)
            );
        }
        for (const option of document.querySelectorAll('[data-language]')) {
            option.setAttribute(
                'aria-pressed',
                String(option.dataset.language === language)
            );
        }
        renderMessage();
    }

    async function setupRedirect() {
        const response = await fetch('/api/setup/status');
        if (!response.ok) return;
        const status = await response.json();
        if (mode === 'login' && status.setup_required) location.replace('/setup');
        if (mode === 'setup' && !status.setup_required) location.replace('/login');
    }

    async function loadPublicIdentity() {
        const response = await fetch('/api/settings/logo');
        if (!response.ok) return;
        const identity = await response.json();
        const logo = document.getElementById('public-logo');
        const logoText = document.getElementById('public-logo-text');
        const loginPage = document.querySelector('.login-page-shell');
        if (logo) {
            logo.onerror = () => {
                logo.onerror = null;
                logo.src = '/brand-mark.svg';
            };
            logo.src = identity.logo_data || '/brand-mark.svg';
            logo.alt = identity.logo_text || 'ChatRaw';
        }
        if (logoText) logoText.textContent = identity.logo_text || 'ChatRaw';
        if (loginPage && identity.login_background_data) {
            const background = new Image();
            try {
                await new Promise((resolve, reject) => {
                    background.onload = resolve;
                    background.onerror = reject;
                    background.src = identity.login_background_data;
                });
                loginPage.style.backgroundImage = `url(${identity.login_background_data})`;
                loginPage.classList.add('has-custom-background');
                const artwork = loginPage.querySelector('.login-field');
                if (artwork) {
                    artwork.dataset.i18nAriaLabel = 'loginCustomBackgroundLabel';
                    artwork.setAttribute('aria-label', text('loginCustomBackgroundLabel'));
                }
            } catch (_error) {
                // Keep the bundled background and its copy when custom image decoding fails.
            }
        }
    }

    for (const option of document.querySelectorAll('[data-language]')) {
        option.addEventListener('click', () => {
            applyLanguage(option.dataset.language, true);
        });
    }
    applyLanguage(language);

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        submitButton.disabled = true;
        showMessage();
        const values = Object.fromEntries(new FormData(form).entries());
        const endpoint = mode === 'setup' ? '/api/setup/admin' : '/api/auth/login';
        try {
            const response = await fetch(endpoint, {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(values)
            });
            const result = await response.json();
            if (!response.ok) {
                showMessage({
                    code: result.code,
                    detail: result.detail,
                    success: false
                });
                submitButton.disabled = false;
                return;
            }
            if (mode === 'setup') {
                showMessage({key: 'administratorCreated', success: true});
                setTimeout(() => location.replace('/login'), 650);
            } else {
                location.replace('/');
            }
        } catch (_error) {
            showMessage({key: 'requestFailed', success: false});
            submitButton.disabled = false;
        }
    });

    setupRedirect().catch(() => {});
    if (mode === 'login') loadPublicIdentity().catch(() => {});
})();
