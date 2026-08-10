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

function createHost({
    deferAnimationFrame = false,
    userActivated = false
} = {}) {
    const animationFrames = [];
    const dom = new JSDOM(`<!doctype html><body>
        <button id="launcher">Open</button>
        <h2 id="plugin-workspace-title" tabindex="-1">Workspace</h2>
        <div id="plugin-workspace-mount"></div>
    </body>`, {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
    });
    const userActivation = {
        isActive: userActivated,
        hasBeenActive: userActivated
    };
    Object.defineProperty(dom.window.navigator, 'userActivation', {
        configurable: true,
        value: userActivation
    });
    dom.window.matchMedia = () => ({ matches: false });
    dom.window.requestAnimationFrame = callback => {
        if (deferAnimationFrame) {
            animationFrames.push(callback);
            return animationFrames.length;
        }
        callback();
        return 1;
    };
    dom.window.marked = { setOptions() {} };
    dom.window.eval(appSource);
    const host = dom.window.app();
    host.installedPlugins = [];
    host.$nextTick = callback => callback();
    host.$refs = {
        extensionPaletteToggle: dom.window.document.getElementById('launcher')
    };
    host.initPluginSystem();
    host.installedPlugins = [
        { id: 'plugin-one', enabled: true },
        { id: 'plugin-two', enabled: true }
    ];
    return {
        dom,
        host,
        ui: dom.window.ChatRawPlugin.ui,
        flushAnimationFrames() {
            while (animationFrames.length > 0) {
                animationFrames.shift()(0);
            }
        },
        setUserActivation(active) {
            userActivation.isActive = active;
            userActivation.hasBeenActive ||= active;
        }
    };
}

function panelDefinition(id, counters) {
    return {
        id,
        title: { en: 'Workspace', zh: '工作台' },
        icon: 'ri-layout-right-line',
        placements: ['right', 'top', 'bottom', 'main'],
        defaultPlacement: 'right',
        mount({ container, placement }) {
            counters.mounts += 1;
            counters.placements.push(placement);
            const input = container.ownerDocument.createElement('input');
            const select = container.ownerDocument.createElement('select');
            const option = container.ownerDocument.createElement('option');
            option.value = 'one';
            option.textContent = 'One';
            select.append(option);
            const button = container.ownerDocument.createElement('button');
            button.textContent = 'Run';
            const onClick = () => {
                counters.clicks += 1;
                input.value = select.value;
            };
            button.addEventListener('click', onClick);
            container.append(input, select, button);
            return () => {
                counters.disposals += 1;
                button.removeEventListener('click', onClick);
            };
        }
    };
}

function collectionPanelDefinition(id, counters, {
    tabOrder,
    title = { en: 'Operations', zh: '运营' },
    icon = 'ri-dashboard-line',
    order = 20
}) {
    return {
        ...panelDefinition(id, counters),
        placements: ['main'],
        defaultPlacement: 'main',
        collection: {
            id: 'operations',
            title,
            icon,
            order,
            tabOrder
        }
    };
}

function counters() {
    return { mounts: 0, disposals: 0, clicks: 0, placements: [] };
}

function catalogCard() {
    return {
        id: 'module-one',
        module_id: 'module-one',
        plugin_id: 'plugin-one',
        panel_id: 'catalog-panel',
        category_id: 'data-hub',
        order: 10,
        title: { en: 'Catalog', zh: '目录' },
        description: { en: 'Catalog card', zh: '目录卡片' },
        icon: 'ri-pulse-line',
        service_ready: true,
        service_reason: null,
        runtime_ready: false,
        available: false,
        state: 'loading'
    };
}

test('catalog availability follows live panel registration and main support', () => {
    const { host, ui } = createHost();
    host.featureCatalog = { categories: [], cards: [catalogCard()] };

    host.recomputeFeatureCatalogRuntime();
    assert.equal(host.featureCatalog.cards[0].state, 'panel_not_registered');

    const rightOnly = panelDefinition('catalog-panel', counters());
    rightOnly.placements = ['right'];
    rightOnly.defaultPlacement = 'right';
    ui.registerWorkspacePanel(rightOnly, 'plugin-one');
    assert.equal(host.featureCatalog.cards[0].state, 'main_placement_required');

    const mainPanel = panelDefinition('catalog-panel', counters());
    mainPanel.placements = ['main'];
    mainPanel.defaultPlacement = 'main';
    ui.registerWorkspacePanel(mainPanel, 'plugin-one');
    assert.equal(host.featureCatalog.cards[0].state, 'available');
    assert.equal(host.featureCatalog.cards[0].runtime_ready, true);
    assert.equal(host.featureCatalog.cards[0].available, true);

    ui.unregisterWorkspacePanel('catalog-panel', 'plugin-one');
    assert.equal(host.featureCatalog.cards[0].state, 'panel_not_registered');
    assert.equal(host.featureCatalog.cards[0].available, false);
});

test('catalog icon is canonical across main workspace presentation', () => {
    const { host, ui } = createHost();
    const card = catalogCard();
    host.featureCatalog = { categories: [], cards: [card] };
    const panel = collectionPanelDefinition(
        'catalog-panel',
        counters(),
        { tabOrder: 10 }
    );
    panel.icon = 'ri-layout-right-line';
    ui.registerWorkspacePanel(panel, 'plugin-one');

    assert.equal(
        host.pluginWorkspacePanelIcon(
            'plugin-one',
            'catalog-panel',
            panel.icon
        ),
        card.icon
    );
    assert.equal(host.pluginWorkspaceCollections[0].panels[0].icon, card.icon);

    ui.openWorkspacePanel(
        'catalog-panel',
        { placement: 'main' },
        'plugin-one'
    );
    assert.equal(
        host.pluginWorkspacePanelIcon(
            host.pluginWorkspace.pluginId,
            host.pluginWorkspace.panelId,
            host.pluginWorkspace.icon
        ),
        card.icon
    );
    assert.match(appHtml, /pluginWorkspacePanelIcon\(/);
    assert.doesNotMatch(
        appHtml,
        /pluginWorkspace\.collectionIcon \|\| pluginWorkspace\.icon/
    );

    assert.equal(
        host.pluginWorkspacePanelIcon(
            'plugin-two',
            'uncatalogued-panel',
            'ri-dashboard-line'
        ),
        'ri-dashboard-line'
    );
});

test('opening settings stops Agent generation and disposes Workspace', () => {
    const { host, ui } = createHost();
    const state = counters();
    const panel = panelDefinition('catalog-panel', state);
    panel.placements = ['main'];
    panel.defaultPlacement = 'main';
    ui.registerWorkspacePanel(panel, 'plugin-one');
    ui.openWorkspacePanel('catalog-panel', { placement: 'main' }, 'plugin-one');
    host.me = { role: 'member' };
    host.agentOpen = true;
    host.agentHistoryOpen = true;
    let aborted = 0;
    host.isGenerating = true;
    host.abortController = { abort() { aborted += 1; } };
    host.markActiveHermesRunCancelled = () => {};

    host.openSettingsPanel();

    assert.equal(aborted, 1);
    assert.equal(host.isGenerating, false);
    assert.equal(host.agentOpen, false);
    assert.equal(host.agentHistoryOpen, false);
    assert.equal(host.pluginWorkspace.show, false);
    assert.equal(state.disposals, 1);
});

test('cancelling settings discards login background draft state', () => {
    const { host } = createHost();
    host.me = { role: 'member' };
    host.settings.ui_settings.login_background_data = 'saved-background';

    host.openSettingsPanel();
    host.loginBackgroundDraft = 'replacement-background';
    host.loginBackgroundAction = 'replace';
    host.cancelSettingsPanel();

    assert.equal(host.showSettings, false);
    assert.equal(
        host.settings.ui_settings.login_background_data,
        'saved-background'
    );
    assert.equal(host.loginBackgroundDraft, 'saved-background');
    assert.equal(host.loginBackgroundAction, 'preserve');
});

test('Plugin management returns to settings without discarding its draft state', async () => {
    const { host } = createHost();
    host.me = { role: 'admin' };
    host.settings.ui_settings.login_background_data = 'saved-background';
    host.loadInstalledPlugins = async () => {};
    host.loadPluginMarket = () => {};

    host.openSettingsPanel();
    host.settingsTab = 'ui';
    host.loginBackgroundDraft = 'replacement-background';
    host.loginBackgroundAction = 'replace';
    await host.openPluginsPanel();

    assert.equal(host.showSettings, false);
    assert.equal(host.showPlugins, true);
    assert.equal(host.settingsTab, 'ui');
    assert.equal(host.loginBackgroundDraft, 'replacement-background');
    assert.equal(host.loginBackgroundAction, 'replace');

    host.closePluginsPanel();

    assert.equal(host.showPlugins, false);
    assert.equal(host.showSettings, true);
    assert.equal(host.settingsTab, 'ui');
    assert.equal(host.loginBackgroundDraft, 'replacement-background');
    assert.equal(host.loginBackgroundAction, 'replace');
});

test('workspace API mounts interactive DOM and closes with one disposal', () => {
    const { dom, host, ui } = createHost();
    const state = counters();
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();

    assert.equal(
        ui.registerWorkspacePanel(
            panelDefinition('inspection', state),
            'plugin-one'
        ),
        true
    );
    assert.equal(
        ui.openWorkspacePanel(
            'inspection',
            { placement: 'right' },
            'plugin-one'
        ),
        true
    );
    const container = dom.window.document.getElementById(
        'plugin-workspace-mount'
    );
    container.querySelector('button').click();
    assert.equal(container.querySelector('input').value, 'one');
    assert.equal(state.clicks, 1);
    assert.equal(state.mounts, 1);
    assert.deepEqual(state.placements, ['right']);
    assert.equal(host.pluginWorkspace.show, true);
    assert.equal(dom.window.document.activeElement, launcher);

    assert.equal(
        ui.closeWorkspacePanel('inspection', 'plugin-one'),
        true
    );
    assert.equal(state.disposals, 1);
    assert.equal(container.children.length, 0);
    assert.equal(host.pluginWorkspace.show, false);
    assert.equal(dom.window.document.activeElement, launcher);
    assert.equal(
        ui.closeWorkspacePanel('inspection', 'plugin-one'),
        false
    );
    assert.equal(state.disposals, 1);
});

test('workspace page survives refresh state and restores after Plugin registration', () => {
    const first = createHost();
    const firstState = counters();
    first.ui.registerWorkspacePanel(
        panelDefinition('refresh-safe', firstState),
        'plugin-one'
    );
    first.ui.openWorkspacePanel(
        'refresh-safe',
        { placement: 'right' },
        'plugin-one'
    );
    const storedPage = first.dom.window.sessionStorage.getItem(
        'chatraw_shell_page_v1'
    );
    assert.deepEqual(JSON.parse(storedPage), {
        kind: 'plugin-workspace',
        pluginId: 'plugin-one',
        panelId: 'refresh-safe',
        placement: 'right'
    });

    const refreshed = createHost();
    refreshed.dom.window.sessionStorage.setItem(
        'chatraw_shell_page_v1',
        storedPage
    );
    const refreshedState = counters();
    refreshed.ui.registerWorkspacePanel(
        panelDefinition('refresh-safe', refreshedState),
        'plugin-one'
    );

    assert.equal(refreshed.host.restorePluginWorkspacePage(), true);
    assert.equal(refreshed.host.pluginWorkspace.show, true);
    assert.equal(refreshed.host.pluginWorkspace.pluginId, 'plugin-one');
    assert.equal(refreshed.host.pluginWorkspace.panelId, 'refresh-safe');
    assert.equal(refreshed.host.pluginWorkspace.placement, 'right');
    assert.equal(refreshedState.mounts, 1);

    refreshed.host.returnHome();
    assert.equal(
        refreshed.dom.window.sessionStorage.getItem('chatraw_shell_page_v1'),
        null
    );
});

test('workspace refresh state fails closed when the saved panel is unavailable', () => {
    const { dom, host } = createHost();
    dom.window.sessionStorage.setItem(
        'chatraw_shell_page_v1',
        JSON.stringify({
            kind: 'plugin-workspace',
            pluginId: 'plugin-one',
            panelId: 'removed-panel',
            placement: 'main'
        })
    );

    assert.equal(host.restorePluginWorkspacePage(), false);
    assert.equal(host.pluginWorkspace.show, false);
    assert.equal(
        dom.window.sessionStorage.getItem('chatraw_shell_page_v1'),
        null
    );
});

test('workspace open options distinguish omission from invalid explicit values', () => {
    const { host, ui } = createHost();
    const state = counters();
    ui.registerWorkspacePanel(
        panelDefinition('placement-contract', state),
        'plugin-one'
    );

    assert.equal(
        ui.openWorkspacePanel(
            'placement-contract',
            {},
            'plugin-one'
        ),
        true
    );
    assert.equal(host.pluginWorkspace.placement, 'right');
    ui.closeWorkspacePanel('placement-contract', 'plugin-one');

    for (const placement of ['', null, false, 0, undefined, 'side']) {
        assert.throws(
            () => ui.openWorkspacePanel(
                'placement-contract',
                { placement },
                'plugin-one'
            ),
            /Unsupported Plugin Workspace placement/
        );
        assert.equal(host.pluginWorkspace.show, false);
    }
});

test('workspace collections group, order, open, switch, and filter panels', () => {
    const { host, ui } = createHost();
    const first = counters();
    const second = counters();
    ui.registerWorkspacePanel(
        collectionPanelDefinition('finance', first, { tabOrder: 20 }),
        'plugin-one'
    );
    ui.registerWorkspacePanel(
        collectionPanelDefinition('video', second, {
            tabOrder: 10,
            title: { zh: '运营', en: 'Operations' }
        }),
        'plugin-two'
    );

    const collection = host.pluginWorkspaceCollections[0];
    assert.equal(collection.id, 'operations');
    assert.deepEqual(
        [...collection.panels].map(
            panel => `${panel.pluginId}:${panel.panelId}`
        ),
        ['plugin-two:video', 'plugin-one:finance']
    );
    ui.openWorkspacePanel('video', { placement: 'main' }, 'plugin-two');
    assert.equal(host.pluginWorkspace.pluginId, 'plugin-two');
    assert.equal(host.pluginWorkspace.panelId, 'video');
    assert.equal(host.pluginWorkspace.collectionId, 'operations');
    assert.equal(host.pluginWorkspace.placement, 'main');
    assert.equal(second.mounts, 1);

    host.switchPluginWorkspaceCollectionPanel(collection.panels[1]);
    assert.equal(second.disposals, 1);
    assert.equal(first.mounts, 1);
    assert.equal(host.pluginWorkspace.pluginId, 'plugin-one');
    assert.equal(host.pluginWorkspace.panelId, 'finance');

    host.installedPlugins.find(plugin => plugin.id === 'plugin-two').enabled = false;
    assert.deepEqual(
        [...host.pluginWorkspaceCollections[0].panels].map(
            panel => `${panel.pluginId}:${panel.panelId}`
        ),
        ['plugin-one:finance']
    );
});

test('workspace collection definitions and tab switches fail closed', () => {
    const { host, ui } = createHost();
    const valid = collectionPanelDefinition(
        'finance',
        counters(),
        { tabOrder: 10 }
    );

    for (const collection of [
        { ...valid.collection, unexpected: true },
        { ...valid.collection, id: '../operations' },
        { ...valid.collection, icon: 'dashboard' },
        { ...valid.collection, order: Number.NaN }
    ]) {
        assert.throws(
            () => ui.registerWorkspacePanel(
                { ...valid, collection },
                'plugin-one'
            ),
            /Invalid Plugin Workspace collection definition/
        );
    }
    assert.throws(
        () => ui.registerWorkspacePanel(
            {
                ...valid,
                placements: ['right', 'main'],
                defaultPlacement: 'right'
            },
            'plugin-one'
        ),
        /Invalid Plugin Workspace collection definition/
    );

    ui.registerWorkspacePanel(valid, 'plugin-one');
    assert.throws(
        () => ui.registerWorkspacePanel(
            collectionPanelDefinition('video', counters(), {
                tabOrder: 20,
                title: 'Different title'
            }),
            'plugin-two'
        ),
        /collection metadata mismatch/
    );
    assert.throws(
        () => host.switchPluginWorkspaceCollectionPanel({
            pluginId: 'plugin-two',
            panelId: 'missing'
        }),
        /collection panel mismatch/
    );
});

test('workspace collection runtime and machine contract stay aligned', () => {
    const definition = pluginUiContract.$defs.WorkspacePanelDefinition;
    const collection = pluginUiContract.$defs.WorkspaceCollectionDefinition;
    assert.equal(
        definition.properties.collection.$ref,
        '#/$defs/WorkspaceCollectionDefinition'
    );
    assert.deepEqual(
        collection.required,
        ['id', 'title', 'icon', 'order', 'tabOrder']
    );
    assert.equal(collection.additionalProperties, false);
    assert.equal(
        definition.allOf[0].then.properties.defaultPlacement.const,
        'main'
    );
    assert.equal(
        definition.allOf[0].then.properties.placements.contains.const,
        'main'
    );
    assert.match(
        pluginUiContract.workspace_collections.lifecycle,
        /dispose-before-mount/
    );
    assert.match(appHtml, /class="plugin-workspace-tabs"/);
    assert.doesNotMatch(appHtml, /openPluginWorkspaceCollection\(/);
    assert.match(appCss, /\.plugin-workspace-tabs button\.active/);
});

test('workspace focus moves only for a synchronous Host entry activation', async () => {
    const {
        dom,
        host,
        ui,
        flushAnimationFrames,
        setUserActivation
    } = createHost({
        deferAnimationFrame: true,
        userActivated: true
    });
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();
    ui.registerWorkspacePanel(
        panelDefinition('deferred-focus', counters()),
        'plugin-one'
    );
    assert.equal(
        ui.registerToolbarButton(
            {
                id: 'open-deferred-focus',
                icon: 'ri-layout-right-line',
                onClick() {
                    return ui.openWorkspacePanel(
                        'deferred-focus',
                        undefined,
                        'plugin-one'
                    );
                }
            },
            'plugin-one'
        ),
        true
    );
    const entry = host.pluginToolbarButtons.find(
        button => button.id === 'open-deferred-focus'
    );

    const firstClick = host.handlePluginButtonClick(entry, launcher);
    assert.equal(dom.window.document.activeElement, launcher);
    flushAnimationFrames();
    assert.equal(
        dom.window.document.activeElement,
        dom.window.document.getElementById('plugin-workspace-title')
    );
    assert.equal(await firstClick, true);

    setUserActivation(false);
    ui.closeWorkspacePanel('deferred-focus', 'plugin-one');
    assert.notEqual(dom.window.document.activeElement, launcher);
    flushAnimationFrames();
    assert.equal(dom.window.document.activeElement, launcher);

    setUserActivation(true);
    const staleClick = host.handlePluginButtonClick(entry, launcher);
    ui.closeWorkspacePanel('deferred-focus', 'plugin-one');
    flushAnimationFrames();
    assert.equal(await staleClick, true);
    assert.equal(dom.window.document.activeElement, launcher);
});

test('palette entry authorizes workspace focus and returns to the stable arrow', async () => {
    const {
        dom,
        host,
        ui,
        flushAnimationFrames
    } = createHost({
        deferAnimationFrame: true,
        userActivated: true
    });
    const entryButton = dom.window.document.getElementById('launcher');
    const paletteArrow = dom.window.document.createElement('button');
    paletteArrow.id = 'palette-arrow';
    dom.window.document.body.append(paletteArrow);
    host.$refs.extensionPaletteToggle = paletteArrow;
    ui.registerWorkspacePanel(
        panelDefinition('palette-open', counters()),
        'plugin-one'
    );
    ui.registerToolbarButton(
        {
            id: 'palette-entry',
            icon: 'ri-layout-right-line',
            onClick() {
                ui.openWorkspacePanel(
                    'palette-open',
                    undefined,
                    'plugin-one'
                );
            }
        },
        'plugin-one'
    );
    const entry = host.pluginToolbarButtons.find(
        button => button.id === 'palette-entry'
    );

    assert.equal(
        await host.handlePluginButtonClick(
            entry,
            entryButton,
            paletteArrow
        ),
        true
    );
    flushAnimationFrames();
    assert.equal(
        dom.window.document.activeElement,
        dom.window.document.getElementById('plugin-workspace-title')
    );
    ui.closeWorkspacePanel('palette-open', 'plugin-one');
    flushAnimationFrames();
    assert.equal(dom.window.document.activeElement, paletteArrow);
});

test('workspace close skips a hidden return arrow and focuses the composer', () => {
    const {
        dom,
        host,
        flushAnimationFrames
    } = createHost({ deferAnimationFrame: true });
    const hiddenArrow = dom.window.document.getElementById('launcher');
    const composer = dom.window.document.createElement('textarea');
    dom.window.document.body.append(composer);
    hiddenArrow.style.display = 'none';
    host.$refs.inputBox = composer;

    host.restorePluginWorkspaceFocus(hiddenArrow);
    flushAnimationFrames();

    assert.equal(dom.window.document.activeElement, composer);
});

test('direct API open preserves focus even during unrelated user activation', () => {
    const {
        dom,
        host,
        ui,
        flushAnimationFrames
    } = createHost({
        deferAnimationFrame: true,
        userActivated: true
    });
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();
    ui.registerWorkspacePanel(
        panelDefinition('background-open', counters()),
        'plugin-one'
    );

    assert.throws(
        () => ui.openWorkspacePanel(
            'background-open',
            { focus: true },
            'plugin-one'
        ),
        /Invalid Plugin Workspace open request/
    );
    assert.equal(host.pluginWorkspace.show, false);

    ui.openWorkspacePanel('background-open', undefined, 'plugin-one');
    flushAnimationFrames();

    assert.equal(host.pluginWorkspace.show, true);
    assert.equal(dom.window.document.activeElement, launcher);

    ui.closeWorkspacePanel('background-open', 'plugin-one');
    flushAnimationFrames();
    assert.equal(dom.window.document.activeElement, launcher);
});

test('async and cross-owner entry callbacks cannot transfer workspace focus', async () => {
    const {
        dom,
        host,
        ui,
        flushAnimationFrames
    } = createHost({
        deferAnimationFrame: true,
        userActivated: true
    });
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();
    ui.registerWorkspacePanel(
        panelDefinition('async-open', counters()),
        'plugin-one'
    );
    ui.registerWorkspacePanel(
        panelDefinition('other-owner', counters()),
        'plugin-two'
    );
    ui.registerToolbarButton(
        {
            id: 'async-entry',
            icon: 'ri-layout-right-line',
            async onClick() {
                await Promise.resolve();
                ui.openWorkspacePanel(
                    'async-open',
                    undefined,
                    'plugin-one'
                );
            }
        },
        'plugin-one'
    );
    const asyncEntry = host.pluginToolbarButtons.find(
        button => button.id === 'async-entry'
    );

    assert.equal(
        await host.handlePluginButtonClick(asyncEntry, launcher),
        true
    );
    flushAnimationFrames();
    assert.equal(host.pluginWorkspace.panelId, 'async-open');
    assert.equal(dom.window.document.activeElement, launcher);
    ui.closeWorkspacePanel('async-open', 'plugin-one');

    ui.registerToolbarButton(
        {
            id: 'cross-owner-entry',
            icon: 'ri-layout-right-line',
            onClick() {
                ui.openWorkspacePanel(
                    'other-owner',
                    undefined,
                    'plugin-two'
                );
            }
        },
        'plugin-one'
    );
    const crossOwnerEntry = host.pluginToolbarButtons.find(
        button => button.id === 'cross-owner-entry'
    );
    assert.equal(
        await host.handlePluginButtonClick(crossOwnerEntry, launcher),
        true
    );
    flushAnimationFrames();
    assert.equal(host.pluginWorkspace.panelId, 'other-owner');
    assert.equal(dom.window.document.activeElement, launcher);
});

test('an entry click can activate an already-open background workspace', async () => {
    const {
        dom,
        host,
        ui,
        flushAnimationFrames
    } = createHost({
        deferAnimationFrame: true,
        userActivated: true
    });
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();
    ui.registerWorkspacePanel(
        panelDefinition('already-open', counters()),
        'plugin-one'
    );
    ui.openWorkspacePanel('already-open', undefined, 'plugin-one');
    flushAnimationFrames();
    assert.equal(dom.window.document.activeElement, launcher);
    ui.registerToolbarButton(
        {
            id: 'activate-existing',
            icon: 'ri-layout-right-line',
            onClick() {
                ui.openWorkspacePanel(
                    'already-open',
                    undefined,
                    'plugin-one'
                );
            }
        },
        'plugin-one'
    );
    const entry = host.pluginToolbarButtons.find(
        button => button.id === 'activate-existing'
    );

    assert.equal(
        await host.handlePluginButtonClick(entry, launcher),
        true
    );
    flushAnimationFrames();
    assert.equal(
        dom.window.document.activeElement,
        dom.window.document.getElementById('plugin-workspace-title')
    );
    ui.closeWorkspacePanel('already-open', 'plugin-one');
    flushAnimationFrames();
    assert.equal(dom.window.document.activeElement, launcher);
});

test('missing browser user-activation support fails closed for focus', async () => {
    const {
        dom,
        host,
        ui,
        flushAnimationFrames
    } = createHost({
        deferAnimationFrame: true,
        userActivated: true
    });
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();
    ui.registerWorkspacePanel(
        panelDefinition('no-user-activation-api', counters()),
        'plugin-one'
    );
    ui.registerToolbarButton(
        {
            id: 'no-user-activation-entry',
            icon: 'ri-layout-right-line',
            onClick() {
                ui.openWorkspacePanel(
                    'no-user-activation-api',
                    undefined,
                    'plugin-one'
                );
            }
        },
        'plugin-one'
    );
    const entry = host.pluginToolbarButtons.find(
        button => button.id === 'no-user-activation-entry'
    );
    delete dom.window.navigator.userActivation;

    assert.equal(
        await host.handlePluginButtonClick(entry, launcher),
        true
    );
    flushAnimationFrames();
    assert.equal(host.pluginWorkspace.show, true);
    assert.equal(dom.window.document.activeElement, launcher);
});

test('workspace disposer must complete synchronously and return undefined', async () => {
    const { dom, host, ui } = createHost();
    const loggedErrors = [];
    let asyncDisposeCalls = 0;
    dom.window.console.error = (...args) => {
        loggedErrors.push(args);
    };
    ui.registerWorkspacePanel(
        {
            ...panelDefinition('async-dispose', counters()),
            mount() {
                return async () => {
                    asyncDisposeCalls += 1;
                    throw new Error('async dispose failed');
                };
            }
        },
        'plugin-one'
    );
    ui.openWorkspacePanel('async-dispose', undefined, 'plugin-one');
    assert.throws(
        () => ui.closeWorkspacePanel(
            'async-dispose',
            'plugin-one'
        ),
        /dispose must complete synchronously and return undefined/
    );
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(host.pluginWorkspace.show, false);
    assert.equal(asyncDisposeCalls, 1);
    assert.equal(
        ui.closeWorkspacePanel('async-dispose', 'plugin-one'),
        false
    );
    assert.equal(asyncDisposeCalls, 1);
    assert.match(
        String(loggedErrors[0]?.[1]),
        /async dispose failed/
    );

    ui.registerWorkspacePanel(
        {
            ...panelDefinition('non-void-dispose', counters()),
            mount() {
                return () => true;
            }
        },
        'plugin-one'
    );
    ui.openWorkspacePanel('non-void-dispose', undefined, 'plugin-one');
    assert.throws(
        () => ui.closeWorkspacePanel(
            'non-void-dispose',
            'plugin-one'
        ),
        /dispose must complete synchronously and return undefined/
    );
    assert.equal(host.pluginWorkspace.show, false);

    ui.registerWorkspacePanel(
        {
            ...panelDefinition('resolved-async-dispose', counters()),
            mount() {
                return async () => {};
            }
        },
        'plugin-one'
    );
    ui.openWorkspacePanel(
        'resolved-async-dispose',
        undefined,
        'plugin-one'
    );
    assert.throws(
        () => ui.closeWorkspacePanel(
            'resolved-async-dispose',
            'plugin-one'
        ),
        /dispose must complete synchronously and return undefined/
    );
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(host.pluginWorkspace.show, false);
});

test('plugin cleanup unregisters panels after an invalid async disposer', async () => {
    const { dom, host, ui } = createHost();
    const loggedErrors = [];
    let disposeCalls = 0;
    dom.window.console.error = (...args) => {
        loggedErrors.push(args);
    };
    ui.registerWorkspacePanel(
        {
            ...panelDefinition('cleanup-async-dispose', counters()),
            mount() {
                return async () => {
                    disposeCalls += 1;
                    throw new Error('cleanup async dispose failed');
                };
            }
        },
        'plugin-one'
    );
    ui.openWorkspacePanel(
        'cleanup-async-dispose',
        undefined,
        'plugin-one'
    );

    host.cleanupPluginRuntime('plugin-one');
    await new Promise(resolve => setImmediate(resolve));

    assert.equal(disposeCalls, 1);
    assert.equal(host.pluginWorkspace.show, false);
    assert.equal(
        host.pluginWorkspaceDefinitions[
            'plugin-one:cleanup-async-dispose'
        ],
        undefined
    );
    assert.ok(
        loggedErrors.some(args => String(args[1]).includes(
            'dispose must complete synchronously'
        ))
    );
    assert.ok(
        loggedErrors.some(args => String(args[1]).includes(
            'cleanup async dispose failed'
        ))
    );
});

test('workspace replacement failure restores the original trigger focus', async () => {
    const { dom, host, ui } = createHost({ userActivated: true });
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();
    ui.registerWorkspacePanel(
        {
            ...panelDefinition('dispose-failure', counters()),
            mount({ container }) {
                const input = container.ownerDocument.createElement('input');
                container.append(input);
                return () => {
                    throw new Error('dispose failed');
                };
            }
        },
        'plugin-one'
    );
    ui.registerWorkspacePanel(
        panelDefinition('replacement', counters()),
        'plugin-two'
    );
    ui.registerToolbarButton(
        {
            id: 'open-dispose-failure',
            icon: 'ri-layout-right-line',
            onClick() {
                ui.openWorkspacePanel(
                    'dispose-failure',
                    undefined,
                    'plugin-one'
                );
            }
        },
        'plugin-one'
    );
    const entry = host.pluginToolbarButtons.find(
        button => button.id === 'open-dispose-failure'
    );
    assert.equal(
        await host.handlePluginButtonClick(entry, launcher),
        true
    );
    dom.window.document.querySelector(
        '#plugin-workspace-mount input'
    ).focus();

    assert.throws(
        () => ui.openWorkspacePanel(
            'replacement',
            undefined,
            'plugin-two'
        ),
        /dispose failed/
    );
    assert.equal(host.pluginWorkspace.show, false);
    assert.equal(host._pluginWorkspaceReturnFocus, null);
    assert.equal(dom.window.document.activeElement, launcher);
});

test('workspace switching is idempotent and disposes before remount', () => {
    const { host, ui } = createHost();
    const first = counters();
    const second = counters();
    ui.registerWorkspacePanel(
        panelDefinition('first', first),
        'plugin-one'
    );
    ui.registerWorkspacePanel(
        panelDefinition('second', second),
        'plugin-two'
    );

    ui.openWorkspacePanel('first', undefined, 'plugin-one');
    ui.openWorkspacePanel('first', undefined, 'plugin-one');
    assert.equal(first.mounts, 1);
    assert.equal(first.disposals, 0);

    ui.openWorkspacePanel('first', { placement: 'top' }, 'plugin-one');
    assert.equal(first.mounts, 2);
    assert.equal(first.disposals, 1);
    assert.deepEqual(first.placements, ['right', 'top']);

    ui.openWorkspacePanel('second', { placement: 'bottom' }, 'plugin-two');
    assert.equal(first.disposals, 2);
    assert.equal(second.mounts, 1);
    assert.equal(host.pluginWorkspace.pluginId, 'plugin-two');
    assert.throws(
        () => ui.closeWorkspacePanel('second', 'plugin-one'),
        /ownership mismatch/
    );
    assert.equal(second.disposals, 0);

    host.cleanupPluginRuntime('plugin-two');
    assert.equal(second.disposals, 1);
    assert.equal(host.pluginWorkspace.show, false);
    assert.equal(
        Object.keys(host.pluginWorkspaceDefinitions).some(
            key => key.startsWith('plugin-two:')
        ),
        false
    );
});

test('workspace registration and mount failures are explicit and leave no DOM', () => {
    const { dom, host, ui } = createHost();
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();
    assert.throws(
        () => ui.registerWorkspacePanel({ id: 'broken' }, 'plugin-one'),
        /Invalid Plugin Workspace definition/
    );
    assert.throws(
        () => ui.registerWorkspacePanel(
            {
                ...panelDefinition('bad-placement', counters()),
                placements: ['right'],
                defaultPlacement: 'top'
            },
            'plugin-one'
        ),
        /Invalid Plugin Workspace definition/
    );
    ui.registerWorkspacePanel(
        {
            ...panelDefinition('no-dispose', counters()),
            mount({ container }) {
                container.append(
                    container.ownerDocument.createElement('button')
                );
            }
        },
        'plugin-one'
    );
    assert.throws(
        () => ui.openWorkspacePanel('no-dispose', undefined, 'plugin-one'),
        /synchronously return dispose/
    );
    assert.equal(host.pluginWorkspace.show, false);
    assert.equal(
        dom.window.document.getElementById('plugin-workspace-mount').children.length,
        0
    );
    assert.equal(dom.window.document.activeElement, launcher);
    assert.throws(
        () => ui.openWorkspacePanel('missing', undefined, 'plugin-one'),
        /not registered/
    );
    assert.throws(
        () => ui.openWorkspacePanel(
            'no-dispose',
            { placement: 'side' },
            'plugin-one'
        ),
        /Unsupported Plugin Workspace placement/
    );
    assert.throws(
        () => ui.registerWorkspacePanel(
            panelDefinition('owner', counters()),
            'not-installed'
        ),
        /owner is not enabled/
    );
    assert.throws(
        () => ui.closeWorkspacePanel('../invalid', 'plugin-one'),
        /Invalid Plugin Workspace panelId/
    );
});

test('workspace lifecycle mutations fail closed during mount and dispose', () => {
    const operations = {
        register(ui) {
            return ui.registerWorkspacePanel(
                panelDefinition('replacement', counters()),
                'plugin-one'
            );
        },
        unregister(ui) {
            return ui.unregisterWorkspacePanel('target', 'plugin-one');
        },
        open(ui) {
            return ui.openWorkspacePanel('target', undefined, 'plugin-one');
        },
        close(ui) {
            return ui.closeWorkspacePanel('target', 'plugin-one');
        }
    };

    for (const [name, operation] of Object.entries(operations)) {
        const mountHost = createHost();
        const mountState = counters();
        mountHost.ui.registerWorkspacePanel(
            panelDefinition('target', counters()),
            'plugin-one'
        );
        mountHost.ui.registerWorkspacePanel(
            {
                ...panelDefinition(`mount-${name}`, mountState),
                mount() {
                    operation(mountHost.ui);
                    return () => {
                        mountState.disposals += 1;
                    };
                }
            },
            'plugin-one'
        );
        assert.throws(
            () => mountHost.ui.openWorkspacePanel(
                `mount-${name}`,
                undefined,
                'plugin-one'
            ),
            /lifecycle cannot change during mount/
        );
        assert.equal(mountHost.host.pluginWorkspace.show, false);
        assert.equal(mountState.disposals, 0);
        assert.ok(
            mountHost.host.pluginWorkspaceDefinitions['plugin-one:target']
        );
        assert.equal(
            mountHost.ui.openWorkspacePanel(
                'target',
                undefined,
                'plugin-one'
            ),
            true
        );
        assert.equal(
            mountHost.ui.closeWorkspacePanel('target', 'plugin-one'),
            true
        );

        const disposeHost = createHost();
        const disposeState = counters();
        disposeHost.ui.registerWorkspacePanel(
            panelDefinition('target', counters()),
            'plugin-one'
        );
        disposeHost.ui.registerWorkspacePanel(
            {
                ...panelDefinition(`dispose-${name}`, disposeState),
                mount() {
                    return () => {
                        disposeState.disposals += 1;
                        operation(disposeHost.ui);
                    };
                }
            },
            'plugin-one'
        );
        disposeHost.ui.openWorkspacePanel(
            `dispose-${name}`,
            undefined,
            'plugin-one'
        );
        assert.throws(
            () => disposeHost.ui.closeWorkspacePanel(
                `dispose-${name}`,
                'plugin-one'
            ),
            /lifecycle cannot change during dispose/
        );
        assert.equal(disposeState.disposals, 1);
        assert.equal(disposeHost.host.pluginWorkspace.show, false);
        assert.ok(
            disposeHost.host.pluginWorkspaceDefinitions['plugin-one:target']
        );
        assert.equal(
            disposeHost.ui.openWorkspacePanel(
                'target',
                undefined,
                'plugin-one'
            ),
            true
        );
        assert.equal(
            disposeHost.ui.closeWorkspacePanel('target', 'plugin-one'),
            true
        );
    }
});

test('workspace layout is non-modal, responsive, and isolated from Alpine', () => {
    assert.match(appHtml, /class="plugin-workspace-layout"/);
    assert.match(appHtml, /role="region"/);
    assert.match(
        appHtml,
        /id="plugin-workspace-title"[\s\S]*?tabindex="-1"/
    );
    assert.doesNotMatch(appHtml, /id="plugin-workspace-close"/);
    assert.match(appHtml, /id="plugin-workspace-mount"[\s\S]*x-ignore/);
    assert.match(appHtml, /@keydown\.escape\.stop="closeActivePluginWorkspace\(\)"/);
    assert.doesNotMatch(
        appHtml.slice(
            appHtml.indexOf('class="plugin-workspace-panel"'),
            appHtml.indexOf('<!-- Toast -->')
        ),
        /aria-modal|modal-overlay/
    );
    assert.match(
        appCss,
        /grid-template-columns:\s*minmax\(0, 1fr\) clamp\(360px, 38vw, 640px\)/
    );
    assert.match(
        appCss,
        /grid-template-rows:\s*clamp\(200px, 32vh, 360px\) minmax\(0, 1fr\)/
    );
    assert.match(appCss, /@media \(max-width: 1024px\)/);
    assert.match(appCss, /@media \(max-height: 420px\)/);
    assert.match(appCss, /contain:\s*layout paint/);
    assert.match(appCss, /isolation:\s*isolate/);
    assert.match(appHtml, /x-ref="extensionPaletteToggle"/);
    assert.match(
        appHtml,
        /class="agent-extension-item"[\s\S]*handleExtensionEntryClick\(entry, \$event\.currentTarget\)/
    );
    assert.match(appCss, /width:\s*min\(100%, 32rem\)/);
    assert.match(appCss, /max-height:\s*min\(18rem, 45dvh\)/);
    assert.match(appCss, /repeat\(auto-fit, minmax\(9rem, 1fr\)\)/);
});

test('focus contract and Host entry wiring describe the same authorization boundary', () => {
    assert.match(
        pluginUiContract.focus.host_focus_authorization,
        /Host-rendered Agent extension palette entry/
    );
    assert.match(
        pluginUiContract.focus.host_focus_authorization,
        /entry pluginId equals the workspace owner/
    );
    assert.match(
        pluginUiContract.focus.unauthorized_open,
        /direct API calls.*asynchronous callback continuations.*cross-owner/s
    );
    assert.match(pluginUiContract.focus.authorized_open, /workspace title/);
    assert.equal(pluginUiContract.focus.plugin_override, false);
    assert.match(
        appHtml,
        /handleExtensionEntryClick\(entry, \$event\.currentTarget\)/
    );
    assert.match(
        appSource,
        /activation\?\.pluginId === owner[\s\S]*navigator\.userActivation\?\.isActive === true/
    );
});

test('plugin lifecycle paths use one shared runtime cleanup', () => {
    assert.match(
        appSource,
        /async loadPluginJS\(plugin\)[\s\S]*?this\.cleanupPluginRuntime\(plugin\.id\)/
    );
    assert.match(
        appSource,
        /async togglePlugin\(plugin\)[\s\S]*?this\.cleanupPluginRuntime\(plugin\.id\)/
    );
    assert.match(
        appSource,
        /async uninstallPlugin\(plugin\)[\s\S]*?this\.cleanupPluginRuntime\(plugin\.id\)/
    );
    assert.doesNotMatch(
        appSource.slice(
            appSource.indexOf('registerPluginWorkspacePanel('),
            appSource.indexOf('// ============ Plugin System')
        ),
        /setInterval|MutationObserver|ResizeObserver/
    );
});

test('plugin runtime synchronization replaces changed versions and removes stale runtimes', async () => {
    const { dom, host } = createHost();
    host.installedPlugins = [
        { id: 'plugin-one', version: '1.0.0', enabled: true },
        { id: 'plugin-removed', version: '1.0.0', enabled: true }
    ];
    host.pluginRuntimeVersions = {
        'plugin-one': '1.0.0',
        'plugin-removed': '1.0.0'
    };
    const loaded = [];
    const cleaned = [];
    host.loadPluginJS = async plugin => {
        loaded.push(`${plugin.id}@${plugin.version}`);
        host.pluginRuntimeVersions[plugin.id] = plugin.version;
    };
    host.cleanupPluginRuntime = pluginId => {
        cleaned.push(pluginId);
        delete host.pluginRuntimeVersions[pluginId];
    };
    dom.window.fetch = async (url, options) => {
        assert.equal(url, '/api/plugins');
        assert.equal(options.credentials, 'same-origin');
        assert.equal(options.cache, 'no-store');
        return {
            ok: true,
            async json() {
                return [
                    { id: 'plugin-one', version: '1.1.0', enabled: true },
                    { id: 'plugin-disabled', version: '2.0.0', enabled: false }
                ];
            }
        };
    };

    await host.syncPluginRuntimes();

    assert.deepEqual(cleaned, ['plugin-removed']);
    assert.deepEqual(loaded, ['plugin-one@1.1.0']);
    assert.deepEqual(
        host.installedPlugins.map(plugin => plugin.id),
        ['plugin-one', 'plugin-disabled']
    );
    assert.equal(host.pluginRuntimeVersions['plugin-one'], '1.1.0');
    assert.equal(host.pluginRuntimeVersions['plugin-removed'], undefined);
});

test('plugin management changes notify other open tabs', () => {
    assert.match(
        appSource,
        /new window\.BroadcastChannel\(\s*'chatraw-plugin-runtime-v1'\s*\)/
    );
    for (const method of [
        'installPlugin',
        'uploadPluginFile',
        'togglePlugin',
        'uninstallPlugin'
    ]) {
        const start = appSource.indexOf(`async ${method}(`);
        const end = appSource.indexOf('\n        },', start);
        assert.ok(start >= 0, `${method} must exist`);
        assert.match(
            appSource.slice(start, end),
            /refreshFeatureCatalogAfterPluginChange\(/
        );
    }
    const refreshStart = appSource.indexOf('async refreshFeatureCatalogAfterPluginChange(');
    const refreshEnd = appSource.indexOf('\n        },', refreshStart);
    assert.match(appSource.slice(refreshStart, refreshEnd), /announcePluginRuntimeChange\(/);
});

test('same-tab plugin toggles refresh the service catalog before broadcasting', async () => {
    const { dom, host } = createHost();
    const plugin = { id: 'plugin-one', enabled: true };
    host.installedPlugins = [plugin];
    host.showToast = () => {};
    let catalogRefreshes = 0;
    let broadcasts = 0;
    host.loadFeatureCatalog = async () => {
        catalogRefreshes += 1;
    };
    host.announcePluginRuntimeChange = () => {
        broadcasts += 1;
    };
    dom.window.fetch = async () => ({ ok: true });

    await host.togglePlugin(plugin);

    assert.equal(plugin.enabled, false);
    assert.equal(catalogRefreshes, 1);
    assert.equal(broadcasts, 1);
});
