import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import { JSDOM } from 'jsdom';


const appSource = fs.readFileSync('backend/static/app.js', 'utf8');
const appHtml = fs.readFileSync('backend/static/index.html', 'utf8');
const appCss = fs.readFileSync('backend/static/styles.css', 'utf8');

function createHost() {
    const dom = new JSDOM(`<!doctype html><body>
        <button id="launcher">Open</button>
        <button id="plugin-workspace-close">Close</button>
        <div id="plugin-workspace-mount"></div>
    </body>`, {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
    });
    dom.window.matchMedia = () => ({ matches: false });
    dom.window.marked = { setOptions() {} };
    dom.window.eval(appSource);
    const host = dom.window.app();
    host.installedPlugins = [];
    host.$nextTick = callback => callback();
    host.initPluginSystem();
    host.installedPlugins = [
        { id: 'plugin-one', enabled: true },
        { id: 'plugin-two', enabled: true }
    ];
    return { dom, host, ui: dom.window.ChatRawPlugin.ui };
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

function counters() {
    return { mounts: 0, disposals: 0, clicks: 0, placements: [] };
}

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
    assert.match(appCss, /contain:\s*layout paint/);
    assert.match(appCss, /isolation:\s*isolate/);
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
