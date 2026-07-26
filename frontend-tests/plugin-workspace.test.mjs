import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import { JSDOM } from 'jsdom';


const appSource = fs.readFileSync('backend/static/app.js', 'utf8');
const appHtml = fs.readFileSync('backend/static/index.html', 'utf8');
const appCss = fs.readFileSync('backend/static/styles.css', 'utf8');

function createHost({ deferAnimationFrame = false } = {}) {
    const animationFrames = [];
    const dom = new JSDOM(`<!doctype html><body>
        <button id="launcher">Open</button>
        <button id="plugin-workspace-close">Close</button>
        <div id="plugin-workspace-mount"></div>
    </body>`, {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
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
        dom.window.document.activeElement,
        dom.window.document.getElementById('plugin-workspace-close')
    );

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

test('workspace focus moves only after visibility updates and ignores stale opens', () => {
    const {
        dom,
        ui,
        flushAnimationFrames
    } = createHost({ deferAnimationFrame: true });
    const launcher = dom.window.document.getElementById('launcher');
    launcher.focus();
    ui.registerWorkspacePanel(
        panelDefinition('deferred-focus', counters()),
        'plugin-one'
    );

    ui.openWorkspacePanel('deferred-focus', undefined, 'plugin-one');
    assert.equal(dom.window.document.activeElement, launcher);
    flushAnimationFrames();
    assert.equal(
        dom.window.document.activeElement,
        dom.window.document.getElementById('plugin-workspace-close')
    );

    ui.closeWorkspacePanel('deferred-focus', 'plugin-one');
    assert.notEqual(dom.window.document.activeElement, launcher);
    flushAnimationFrames();
    assert.equal(dom.window.document.activeElement, launcher);

    ui.openWorkspacePanel('deferred-focus', undefined, 'plugin-one');
    ui.closeWorkspacePanel('deferred-focus', 'plugin-one');
    flushAnimationFrames();
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

test('workspace replacement failure restores the original trigger focus', () => {
    const { dom, host, ui } = createHost();
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
    ui.openWorkspacePanel('dispose-failure', undefined, 'plugin-one');
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
