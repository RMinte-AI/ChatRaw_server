import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import { JSDOM } from 'jsdom';

const html = fs.readFileSync('backend/static/index.html', 'utf8');
const app = fs.readFileSync('backend/static/app.js', 'utf8');
const styles = fs.readFileSync('backend/static/styles.css', 'utf8');

test('home exposes the confirmed three hubs and Host catalog cards', () => {
    assert.match(html, /class="hub-home"/);
    assert.match(html, /featureCatalog\.categories/);
    assert.match(html, /activeFeatureCards/);
    assert.match(app, /fetch\('\/api\/module-feature-catalog'\)/);
    assert.match(styles, /\.hub-card-grid/);
});

test('home preserves the approved asymmetric bento card rhythm', () => {
    assert.match(styles, /\.hub-card-grid\s*\{[^}]*grid-template-columns:\s*repeat\(12,/s);
    assert.match(styles, /\.hub-card:nth-of-type\(1\)\s*\{[^}]*grid-column:\s*span 7/s);
    assert.match(styles, /\.hub-card:nth-of-type\(2\)\s*\{[^}]*grid-column:\s*span 5/s);
    assert.match(styles, /\.hub-card:nth-of-type\(3\)\s*\{[^}]*grid-column:\s*span 4/s);
    assert.match(styles, /\.hub-card:nth-of-type\(4\)\s*\{[^}]*grid-column:\s*span 5/s);
    assert.match(styles, /\.hub-card:nth-of-type\(5\)\s*\{[^}]*grid-column:\s*span 3/s);
    assert.match(styles, /\.hub-card:nth-of-type\(6\)\s*\{[^}]*grid-column:\s*span 12/s);
    assert.match(styles, /@media \(max-width:\s*980px\)[\s\S]*?\.hub-card:nth-of-type\(n\)\s*\{[^}]*grid-column:\s*span 6/);
    assert.match(styles, /@media \(max-width:\s*760px\)[\s\S]*?\.hub-card:nth-of-type\(n\)\s*\{[^}]*grid-column:\s*1 \/ -1/);
});

test('home color tokens preserve the warm light palette and readable muted text', () => {
    assert.match(styles, /--hub-paper:\s*#f7f6f3/);
    assert.match(styles, /--hub-surface:\s*#ffffff/);
    assert.match(styles, /--hub-ink:\s*#111111/);
    assert.match(styles, /--hub-muted:\s*#726f69/);
    assert.match(styles, /--hub-green:\s*#dde9db/);
    assert.match(styles, /--hub-blue:\s*#dcecf4/);
    assert.match(styles, /--hub-sand:\s*#f3e6c4/);
});

test('home keeps the brand, category tabs, and cards in a compact upper rhythm', () => {
    assert.match(styles, /\.hub-main\s*\{[^}]*margin:\s*-24px auto 0/s);
    assert.match(styles, /\.hub-brand-block\s*\{[^}]*margin:\s*10px auto 24px/s);
    assert.match(styles, /\.hub-brand\s*\{[^}]*margin:\s*0 auto/s);
    assert.match(styles, /\.hub-card-grid\s*\{[^}]*padding:\s*28px 0 40px/s);
    assert.match(
        styles,
        /@media \(max-width:\s*760px\)[\s\S]*?\.hub-brand-block\s*\{[^}]*margin:\s*14px auto 22px/
    );
});

test('home renders the saved subtitle under the central logo', () => {
    const brandBlock = html.slice(
        html.indexOf('class="hub-brand-block"'),
        html.indexOf('class="hub-tabs"')
    );
    assert.match(brandBlock, /class="hub-brand"/);
    assert.match(brandBlock, /class="hub-subtitle"/);
    assert.match(brandBlock, /settings\.ui_settings\.subtitle\?\.trim\(\)/);
    assert.match(brandBlock, /x-text="settings\.ui_settings\.subtitle"/);
    assert.match(styles, /\.hub-subtitle\s*\{[^}]*text-wrap:\s*balance/s);
});

test('Interface settings expose the login background upload and clear controls', () => {
    const document = new JSDOM(html).window.document;
    const fileInput = [...document.querySelectorAll('input[type="file"]')]
        .find(input => input.getAttribute('@change') === 'handleLoginBackgroundUpload($event)');
    const clearButton = [...document.querySelectorAll('button')]
        .find(button => button.getAttribute('@click') === 'clearLoginBackground()');

    assert.ok(fileInput);
    assert.equal(
        fileInput.getAttribute('accept'),
        'image/jpeg,image/png,image/webp'
    );
    assert.ok(clearButton);
    assert.match(app, /login_background_data:\s*''/);
    assert.match(app, /LOGIN_BACKGROUND_INPUT_MAX_BYTES\s*=\s*15 \* 1024 \* 1024/);
    assert.match(app, /LOGIN_BACKGROUND_OUTPUT_MAX_BYTES\s*=\s*4 \* 1024 \* 1024/);
    assert.match(app, /handleLoginBackgroundUpload\(event\)/);
    assert.match(app, /prepareLoginBackground\(file\)/);
    assert.match(app, /clearLoginBackground\(\)/);
    assert.match(app, /login_background_action\s*=\s*backgroundAction/);
    assert.match(styles, /\.login-background-preview\s*\{[^}]*object-fit:\s*cover/s);
});

test('the only conversation surface is the SDHS Agent popup', () => {
    assert.match(html, /class="agent-launcher"/);
    assert.match(html, /SDHS Agent/);
    assert.match(html, /class="agent-history"/);
    assert.match(html, /class="agent-modal-backdrop"/);
    assert.match(html, /class="agent-window-toggle"/);
    assert.match(html, /toggleAgentExpanded\(\)/);
    assert.doesNotMatch(html, /class="thinking-toggle"/);
    assert.match(html, /<h1>SDHS Agent<\/h1>/);
    assert.match(app, /const AGENT_CHAT_ENDPOINT = '\/api\/agent\/chat'/);
    assert.match(app, /fetch\(AGENT_CHAT_ENDPOINT/);
    assert.match(app, /agentExpanded: false/);
    assert.match(app, /toggleAgentExpanded\(\)/);
    assert.doesNotMatch(app, /useThinking/);
    assert.match(app, /fetch\('\/api\/agent\/chats'/);
    assert.doesNotMatch(app, /const endpoint = await this\.resolveMessageRouteEndpoint\(body\)/);
    const sendMessage = app.split('async sendMessage() {')[1].split('async handleStreamResponse', 1)[0];
    assert.doesNotMatch(sendMessage, /callSendInterceptors/);
    assert.doesNotMatch(sendMessage, /transform_input/);
    assert.doesNotMatch(sendMessage, /after_receive/);
    assert.doesNotMatch(sendMessage, /use_thinking/);
});

test('Agent header and history actions keep their intended order and roles', () => {
    const document = new JSDOM(html).window.document;
    const headerButtons = [
        ...document.querySelectorAll('.agent-header > div:last-child > button')
    ];
    const historyHeaderButton = document.querySelector(
        '.agent-history > header > button'
    );
    const historyHeading = document.querySelector(
        '.agent-history > header > span'
    );

    assert.equal(headerButtons[0].getAttribute('@click'), 'createNewChat()');
    assert.equal(
        headerButtons[0].getAttribute(':aria-label'),
        "t('newConversation')"
    );
    assert.equal(headerButtons[1].getAttribute('@click'), 'toggleAgentHistory()');
    assert.equal(
        headerButtons[1].getAttribute(':aria-label'),
        "t('conversationHistory')"
    );
    assert.equal(
        historyHeaderButton.getAttribute('@click'),
        'clearAllChats()'
    );
    assert.equal(
        historyHeaderButton.getAttribute(':aria-label'),
        "t('clearAllChats')"
    );
    assert.equal(
        historyHeaderButton.getAttribute(':title'),
        "t('clearAllChats')"
    );
    assert.equal(
        historyHeaderButton.getAttribute(':disabled'),
        'isClearingChats || chats.length === 0'
    );
    assert.equal(
        historyHeaderButton.querySelector('i').className,
        'ri-delete-bin-line'
    );
    assert.equal(
        historyHeading.getAttribute('x-text'),
        "t('conversationHistory')"
    );
    assert.equal(document.querySelector('.agent-history > header > strong'), null);
    assert.match(
        styles,
        /\.agent-history > div > \.agent-chat-title\s*\{[^}]*padding:\s*0 12px/s
    );
    assert.match(html, /class="agent-chat-title"/);
    assert.doesNotMatch(styles, /\.agent-history > div button:first-child/);
    assert.match(
        styles,
        /\.agent-history header\s*\{[^}]*padding:\s*4px 0 10px 6px/s
    );
    assert.match(
        styles,
        /\.agent-history header button\s*\{[^}]*width:\s*34px/s
    );
    assert.match(html, /class="agent-chat-rename-input"/);
    assert.match(html, /maxlength="200"/);
    assert.match(html, /@keydown\.enter\.prevent="submitRenameChat\(chat\)"/);
    assert.match(html, /@keydown\.escape\.prevent="cancelRenameChat\(\)"/);
    assert.doesNotMatch(html, /class="agent-conversation-dialog"/);
    assert.doesNotMatch(app, /window\.prompt\(this\.t\('renameSharedChat'/);
    assert.match(
        styles,
        /\.message\.user\s*\{[^}]*padding-inline-start:\s*calc\([\s\S]*var\(--message-avatar-size\)[\s\S]*var\(--message-gap\)/s
    );
    assert.doesNotMatch(
        styles,
        /\.message\.user \.message-content\s*\{[^}]*flex:\s*0/s
    );
    assert.match(
        styles,
        /\.chat-container \.message\s*\{[^}]*--message-avatar-size:\s*30px;[^}]*--message-gap:\s*9px;[^}]*gap:\s*var\(--message-gap\)/s
    );
});

test('Agent launcher and title identity use round pale-blue Host accents', () => {
    assert.match(
        styles,
        /\.agent-launcher\s*\{[^}]*width:\s*48px;[^}]*height:\s*48px;[^}]*background:\s*var\(--hub-blue\);[^}]*border:\s*1px solid var\(--hub-line\);[^}]*border-radius:\s*50%/s
    );
    assert.match(
        styles,
        /\.agent-mark\s*\{[^}]*width:\s*40px;[^}]*height:\s*40px;[^}]*background:\s*var\(--hub-blue\);[^}]*border:\s*1px solid var\(--hub-line\);[^}]*border-radius:\s*50%/s
    );
    assert.doesNotMatch(styles, /\.agent-launcher\s*\{[^}]*background:\s*#111/s);
    assert.doesNotMatch(styles, /\.agent-mark\s*\{[^}]*background:\s*#111/s);
});

test('settings and Plugin Workspace are independent full-page views', () => {
    const settingsModalRules = [
        ...styles.matchAll(
            /body > \.modal-overlay\[aria-labelledby="settings-modal-title"\] \.settings-modal\s*\{([^}]*)\}/g
        )
    ];
    const settingsModalOverflowRules = settingsModalRules.filter(match =>
        /overflow\s*:/.test(match[1])
    );

    assert.match(html, /class="settings-page-back"/);
    assert.match(html, /class="content-navigator"/);
    assert.match(html, /x-show="pluginWorkspace\.show \|\| agentOpen"/);
    assert.match(styles, /Four-page shell layout/);
    assert.doesNotMatch(html, /class="sidebar"/);
    assert.doesNotMatch(html, /theme_mode = 'dark'/);
    assert.match(styles, /Public compatibility tokens only/);
    assert.match(app, /setAttribute\('data-theme', 'light'\)/);
    assert.doesNotMatch(
        styles,
        /\.chat-container\s*\{[^}]*display:\s*flex\s*!important/s
    );
    assert.doesNotMatch(styles, /\.content-navigator\s*\{[^}]*display:\s*flex\s*!important/s);
    assert.doesNotMatch(styles, /\.plugin-workspace-panel\s*\{[^}]*display:\s*flex\s*!important/s);
    assert.doesNotMatch(styles, />\s*\.chat-container\s*\{[^}]*display:\s*none/s);
    assert.match(styles, /height:\s*min\(620px,\s*calc\(100dvh - 112px\)\)\s*!important/);
    assert.match(
        styles,
        /body > \.modal-overlay\[aria-labelledby="settings-modal-title"\] \.settings-content\s*\{[^}]*background:\s*var\(--hub-paper\)/s
    );
    assert.doesNotMatch(
        styles,
        /body > \.modal-overlay\[aria-labelledby="settings-modal-title"\] \.settings-modal\s*\{[^}]*background:\s*#fff/s
    );
    assert.ok(settingsModalOverflowRules.length > 0);
    assert.match(
        settingsModalOverflowRules.at(-1)[1],
        /overflow:\s*hidden/
    );
});

test('every Plugin Workspace title uses a compact centered module header', () => {
    const workspaceHeaderRules = [
        ...styles.matchAll(/\.plugin-workspace-header\s*\{([^}]*)\}/g)
    ];

    assert.match(
        styles,
        /\.plugin-workspace-header\s*\{[^}]*justify-content:\s*center/s
    );
    assert.match(workspaceHeaderRules.at(-1)[1], /min-height:\s*52px/);
    assert.match(html, /class="plugin-workspace-heading"/);
});

test('settings controls use the shell button hierarchy and keyboard focus', () => {
    const settingsNav = html.slice(
        html.indexOf('class="settings-nav"'),
        html.indexOf('class="settings-footer"')
    );
    assert.equal((settingsNav.match(/<button class="nav-item"/g) || []).length, 7);
    assert.match(
        settingsNav,
        /x-show="isAdmin\(\)"[^>]*@click="openPluginsPanel\(\)"[^>]*x-text="t\('plugins'\)"/
    );
    assert.match(
        html,
        /x-show="showPlugins"[^>]*@click\.self="closePluginsPanel\(\)"[^>]*@keydown\.escape\.window="showPlugins && closePluginsPanel\(\)"/
    );
    assert.match(
        html,
        /<button class="btn-secondary" @click="closePluginsPanel\(\)" x-text="t\('close'\)"><\/button>/
    );
    assert.match(
        styles,
        /aria-labelledby="settings-modal-title"[^}]*:is\(\.btn-primary, \.btn-secondary, \.btn-danger, \.btn-delete\)[^{]*\{[^}]*min-height:\s*44px/s
    );
    assert.match(styles, /\.nav-item\.active\s*\{[^}]*background:\s*#edf4ec/s);
    assert.match(styles, /\.modal-actions-bar\s*\{[^}]*background:\s*var\(--hub-paper\)/s);
    assert.match(styles, /\.toggle-switch:focus-visible\s*\{[^}]*outline:\s*2px solid #315f3a/s);
    assert.match(styles, /:is\(\.btn-danger, \.btn-delete\)\s*\{[^}]*opacity:\s*1/s);
});

test('settings footers expose the AGPL license and corresponding source', () => {
    assert.equal((html.match(/2026 ChatRaw Server by /g) || []).length, 2);
    assert.equal((html.match(/href="https:\/\/github\.com\/massif-01"/g) || []).length, 2);
    assert.equal((html.match(/>massif-01<\/a>/g) || []).length, 2);
    assert.equal((html.match(/x-text="t\('agplLicense'\)"/g) || []).length, 2);
    assert.equal((html.match(/class="settings-footer-github"/g) || []).length, 2);
    assert.equal((html.match(/class="ri-github-fill"/g) || []).length, 2);
    assert.equal((html.match(/:aria-label="t\('sourceCode'\)"/g) || []).length, 2);
    assert.match(app, /agplLicense: 'GNU AGPL-3\.0'/);
    assert.doesNotMatch(app, /legalNotice/);
    assert.doesNotMatch(app, /No warranty/);
    assert.doesNotMatch(app, /不提供担保/);
    assert.doesNotMatch(html, /opensource\.org\/licenses\/MIT/);
    assert.doesNotMatch(app, /mitLicense/);
});

test('catalog availability requires live main-placement panel registration', () => {
    assert.match(app, /recomputeFeatureCatalogRuntime\(\)/);
    assert.match(app, /state: 'panel_not_registered'/);
    assert.match(app, /state: 'main_placement_required'/);
    assert.match(app, /const placement = 'main'/);
});

test('initialization restores the saved page only after enabled Plugins load', () => {
    const initBody = app.slice(
        app.indexOf('async init() {'),
        app.indexOf('\n        initCrossTabStateSync()', app.indexOf('async init() {'))
    );
    assert.match(
        initBody,
        /await this\.initPluginSystem\(\);[\s\S]*this\.restorePluginWorkspacePage\(\);/
    );
    const pluginInitBody = app.slice(
        app.indexOf('initPluginSystem() {'),
        app.indexOf('\n        initPluginRuntimeSync()', app.indexOf('initPluginSystem() {'))
    );
    assert.match(
        pluginInitBody,
        /this\.initPluginRuntimeSync\(\);[\s\S]*return this\.loadEnabledPlugins\(\);/
    );
});

test('installed plugins without a declared icon do not request a missing resource', () => {
    assert.match(html, /<template x-if="plugin\.icon">/);
    assert.match(html, /x-show="!plugin\.icon"/);
});

test('all shell logo surfaces fall back to the bundled mark after an image error', () => {
    assert.match(app, /handleLogoImageError\(event\)/);
    assert.equal((html.match(/@error="handleLogoImageError\(\$event\)"/g) || []).length, 4);
});

test('Agent response handlers preserve the dedicated endpoint at the network boundary', async () => {
    const dom = new JSDOM('<!doctype html><body></body>', {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
    });
    dom.window.matchMedia = () => ({ matches: false });
    dom.window.marked = { setOptions() {} };
    dom.window.eval(app);
    const host = dom.window.app();
    const requests = [];
    dom.window.fetch = async endpoint => {
        requests.push(endpoint);
        return {
            ok: true,
            async json() {
                return { chat_id: 'agent-chat', content: 'ok' };
            }
        };
    };
    host.$nextTick = callback => callback();
    host.$refs = {};

    await host.handleNormalResponse({}, new AbortController().signal);

    assert.deepEqual(requests, ['/api/agent/chat']);
    assert.equal(host.currentChatId, 'agent-chat');
});
