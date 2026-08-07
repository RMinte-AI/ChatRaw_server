import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import { JSDOM } from 'jsdom';


const appSource = fs.readFileSync('backend/static/app.js', 'utf8');
const appHtml = fs.readFileSync('backend/static/index.html', 'utf8');
const appCss = fs.readFileSync('backend/static/styles.css', 'utf8');
const pluginUiContract = JSON.parse(
    fs.readFileSync('backend/contracts/plugin-ui-sdk-v1.json', 'utf8')
);
const residentSdkContract = JSON.parse(
    fs.readFileSync('backend/contracts/resident-integration-sdk-v1.json', 'utf8')
);

function createApp() {
    const dom = new JSDOM(`<!doctype html><body>
        <section id="agent-extension-palette">
            <button class="agent-extension-item">Extension</button>
        </section>
        <button id="extension-toggle">Extensions</button>
        <textarea id="input-box"></textarea>
        <button id="agent-launcher">Agent</button>
    </body>`, {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
    });
    dom.window.matchMedia = () => ({ matches: false });
    dom.window.requestAnimationFrame = callback => {
        callback(0);
        return 1;
    };
    dom.window.marked = { setOptions() {} };
    dom.window.eval(appSource);
    const host = dom.window.app();
    host.lang = 'zh';
    host.$nextTick = callback => callback();
    host.$refs = {
        extensionPaletteToggle: dom.window.document.getElementById('extension-toggle'),
        inputBox: dom.window.document.getElementById('input-box'),
        agentLauncher: dom.window.document.getElementById('agent-launcher')
    };
    return { dom, host };
}

test('extension palette preserves separate Plugin and Resident authority', () => {
    const { host } = createApp();
    host.installedPlugins = [
        { id: 'plugin-one', enabled: true },
        { id: 'hermes', enabled: true },
        { id: 'plugin-disabled', enabled: false }
    ];
    host.pluginToolbarButtons = [
        {
            fullId: 'plugin-one:run',
            pluginId: 'plugin-one',
            id: 'run',
            icon: 'ri-play-line',
            label: { zh: '插件动作', en: 'Plugin action' },
            order: 50,
            placement: 'toolbar',
            active: true,
            loading: false,
            disabled: false
        },
        {
            fullId: 'hermes:route',
            pluginId: 'hermes',
            id: 'route',
            icon: 'ri-robot-line',
            label: { zh: 'Hermes', en: 'Hermes' },
            order: 1,
            placement: 'toolbar',
            active: false,
            loading: false,
            disabled: false
        },
        {
            fullId: 'plugin-disabled:run',
            pluginId: 'plugin-disabled',
            id: 'run',
            icon: 'ri-close-line',
            label: { zh: '已停用', en: 'Disabled' },
            order: 2,
            placement: 'toolbar',
            active: false,
            loading: false,
            disabled: false
        }
    ];
    host.residentIntegrations = [
        {
            id: 'resident-one',
            name: { zh: '常驻能力', en: 'Resident feature' },
            feature: { visible: true, available: false },
            entrypoints: [
                {
                    id: 'open',
                    placement: 'composer',
                    icon: 'ri-layout-line',
                    label: { zh: '常驻能力', en: 'Resident feature' },
                    order: 50
                }
            ]
        }
    ];

    const entries = host.extensionPaletteEntries;
    assert.deepEqual(Array.from(entries, entry => entry.key), [
        'resident:resident-one:open',
        'plugin:plugin-one:run'
    ]);
    assert.equal(entries[0].disabled, true);
    assert.equal(entries[0].status, '不可用');
    assert.equal(entries[1].active, true);
    assert.equal(entries[1].source, host.pluginToolbarButtons[0]);
});

test('an empty dynamic registry closes the extension palette', () => {
    const { host } = createApp();
    host.showExtensionPalette = true;
    host.syncExtensionPaletteVisibility(0);
    assert.equal(host.showExtensionPalette, false);
});

test('an orphan Plugin registration is never visible or callable', async () => {
    const { host } = createApp();
    let calls = 0;
    host.installedPlugins = [];
    host.pluginToolbarButtons = [{
        fullId: 'removed-plugin:run',
        pluginId: 'removed-plugin',
        id: 'run',
        icon: 'ri-play-line',
        label: { zh: '已移除插件' },
        order: 1,
        placement: 'toolbar',
        onClick() { calls += 1; }
    }];

    assert.deepEqual(Array.from(host.extensionPaletteEntries), []);
    assert.equal(await host.handleExtensionEntryClick({
        key: 'plugin:removed-plugin:run'
    }), false);
    assert.equal(calls, 0);
});

test('opening the palette focuses its first enabled entry', () => {
    const { dom, host } = createApp();
    host.installedPlugins = [{ id: 'plugin-one', enabled: true }];
    host.pluginToolbarButtons = [{
        fullId: 'plugin-one:run',
        pluginId: 'plugin-one',
        id: 'run',
        icon: 'ri-play-line',
        label: { zh: '运行' },
        order: 1,
        placement: 'toolbar'
    }];

    host.toggleExtensionPalette();
    assert.equal(host.showExtensionPalette, true);
    assert.equal(
        dom.window.document.activeElement,
        dom.window.document.querySelector('.agent-extension-item')
    );
});

test('the presentation model remains stable for small and large registries', () => {
    for (const count of [1, 6, 20]) {
        const { host } = createApp();
        host.installedPlugins = Array.from({ length: count }, (_, index) => ({
            id: `plugin-${index}`,
            enabled: true
        }));
        host.pluginToolbarButtons = Array.from({ length: count }, (_, index) => ({
            fullId: `plugin-${index}:run`,
            pluginId: `plugin-${index}`,
            id: 'run',
            icon: 'ri-play-line',
            label: { zh: `扩展入口 ${index}` },
            order: count - index,
            placement: 'toolbar'
        }));

        const entries = host.extensionPaletteEntries;
        assert.equal(entries.length, count);
        assert.deepEqual(
            Array.from(entries, entry => entry.order),
            Array.from({ length: count }, (_, index) => index + 1)
        );
    }
});

test('removing the final entry returns focus to the visible composer', () => {
    const { dom, host } = createApp();
    const toggle = host.$refs.extensionPaletteToggle;
    toggle.focus();
    toggle.style.display = 'none';
    host.showExtensionPalette = true;

    host.syncExtensionPaletteVisibility(0);

    assert.equal(host.showExtensionPalette, false);
    assert.equal(dom.window.document.activeElement, host.$refs.inputBox);
});

test('a stale entry snapshot cannot invoke an unregistered callback', async () => {
    const { host } = createApp();
    let calls = 0;
    host.installedPlugins = [{ id: 'plugin-one', enabled: true }];
    host.pluginToolbarButtons = [{
        fullId: 'plugin-one:run',
        pluginId: 'plugin-one',
        id: 'run',
        icon: 'ri-play-line',
        label: { zh: '运行' },
        order: 1,
        placement: 'toolbar',
        onClick() { calls += 1; }
    }];
    const snapshot = host.extensionPaletteEntries[0];
    host.pluginToolbarButtons = [];

    assert.equal(await host.handleExtensionEntryClick(snapshot), false);
    assert.equal(calls, 0);
});

test('the composer has three core actions and one conditional palette trigger', () => {
    assert.doesNotMatch(appHtml, /<template x-if="chatModelSupportsVision\(\)">/);
    assert.match(appHtml, /:disabled="!chatModelSupportsVision\(\)"/);
    const toolbar = appHtml.slice(
        appHtml.indexOf('<div class="input-toolbar">'),
        appHtml.indexOf('<!-- Send Button -->')
    );
    assert.match(toolbar, /handleImageUpload/);
    assert.match(toolbar, /handleDocumentUpload/);
    assert.match(toolbar, /toggleUrlInput/);
    assert.match(toolbar, /x-ref="imageUploadInput"/);
    assert.match(toolbar, /x-ref="documentUploadInput"/);
    assert.match(
        toolbar,
        /<button class="btn-tool btn-tool-upload"[\s\S]*?\$refs\.imageUploadInput\?\.click\(\)/
    );
    assert.match(
        toolbar,
        /<button class="btn-tool btn-tool-upload"[\s\S]*?\$refs\.documentUploadInput\?\.click\(\)/
    );
    assert.doesNotMatch(toolbar, /<label class="btn-tool btn-tool-upload"/);
    assert.match(toolbar, /x-ref="extensionPaletteToggle"/);
    assert.doesNotMatch(toolbar, /plugin-btn|resident-composer-entry/);
    assert.match(appHtml, /class="agent-extension-palette"/);
    assert.match(
        appHtml,
        /@keydown\.escape\.window="showExtensionPalette && closeExtensionPalette\(true\)"/
    );
    assert.match(appCss, /\.btn-tool:disabled/);
});

test('message avatars are square and Agent sizing uses one variable', () => {
    assert.match(
        appCss,
        /\.message-avatar\s*\{[\s\S]*?flex:\s*0 0 var\(--message-avatar-size\)/
    );
    assert.match(
        appCss,
        /\.message-avatar\s*\{[\s\S]*?min-height:\s*var\(--message-avatar-size\)/
    );
    assert.match(appCss, /aspect-ratio:\s*1/);
    assert.match(
        appCss,
        /\.chat-container \.message\s*\{\s*--message-avatar-size:\s*30px;/
    );
    assert.doesNotMatch(
        appCss,
        /\.chat-container \.message-avatar\s*\{[^}]*width:/
    );
});

test('only the Plugin presentation contract changes version', () => {
    assert.equal(pluginUiContract.version, '1.3.0');
    assert.equal(residentSdkContract.version, '1.0.0');
    assert.match(
        pluginUiContract.$defs.ToolbarButtonDefinition.properties.placement.description,
        /extension palette/
    );
    assert.match(residentSdkContract.mount_contract.placement_behavior, /extension palette/);
});
