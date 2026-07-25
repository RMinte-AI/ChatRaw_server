import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

const appScript = fs.readFileSync('backend/static/app.js', 'utf8');
const appHtml = fs.readFileSync('backend/static/index.html', 'utf8');

test('core settings sections and task center use translation bindings', () => {
    for (const binding of [
        "t('users')",
        "t('modules')",
        "t('account')",
        "t('userManagement')",
        "t('featureSuites')",
        "t('moduleTask')",
        "t('approvalRequired')"
    ]) {
        assert.match(appHtml, new RegExp(binding.replace(/[()']/g, '\\$&')));
    }

    assert.doesNotMatch(appHtml, />User management</);
    assert.doesNotMatch(appHtml, />Feature suites</);
    assert.doesNotMatch(appHtml, />Change password</);
    assert.doesNotMatch(appHtml, />\s*Clear key\s*</);
    assert.doesNotMatch(appHtml, /\$\{artifact\.size\} bytes/);
    assert.doesNotMatch(appHtml, /alt="(?:User|AI)"/);
    assert.doesNotMatch(appHtml, /aria-label="(?:Settings navigation|Module tasks|Task progress)"/);
});

test('ordinary account settings expose the shared language selector', () => {
    const accountSection = appHtml.slice(
        appHtml.indexOf(`x-show="settingsTab === 'account'"`),
        appHtml.indexOf('<!-- Modal Actions Footer -->')
    );
    assert.match(accountSection, /setLanguage\('en'\)/);
    assert.match(accountSection, /setLanguage\('zh'\)/);
    assert.match(accountSection, /t\('language'\)/);
});

test('language changes synchronize storage and document metadata', () => {
    assert.match(appScript, /document\.documentElement\.lang = this\.lang === 'zh' \? 'zh-CN' : 'en'/);
    assert.match(appScript, /localStorage\.setItem\('justchat_lang', this\.lang\)/);
    assert.match(appScript, /this\.setLanguage\(this\.lang\)/);
});

test('known API errors are code-first and raw error text is not rendered', () => {
    for (const code of [
        'invalid_username_length',
        'username_in_use',
        'invalid_credentials',
        'current_password_incorrect',
        'last_active_admin'
    ]) {
        assert.match(appScript, new RegExp(`${code}:`));
    }
    assert.doesNotMatch(appScript, /showToast\(error\.message/);
    assert.doesNotMatch(appScript, /moduleTaskUi\.error = error\.message/);
    assert.doesNotMatch(appScript, /progressMessage = event\.data\.message/);
});

test('Chinese dictionary covers core account, module, and task surfaces', () => {
    for (const text of [
        "users: '用户'",
        "modules: '模块'",
        "account: '账户'",
        "featureSuites: '功能套件'",
        "approvalRequired: '需要审批'",
        "invalidCredentials: '用户名或密码错误'"
    ]) {
        assert.match(appScript, new RegExp(text.replace(/[()']/g, '\\$&')));
    }
});
