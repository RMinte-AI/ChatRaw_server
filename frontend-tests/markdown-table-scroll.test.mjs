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

function createHost() {
    const dom = new JSDOM('<!doctype html><body></body>', {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
    });
    dom.window.matchMedia = () => ({ matches: false });
    dom.window.marked = { setOptions() {} };
    dom.window.eval(appSource);
    return {
        document: dom.window.document,
        host: dom.window.app()
    };
}

function createScrollableTable(document) {
    const scroller = document.createElement('div');
    scroller.className = 'markdown-table-scroll';
    const table = document.createElement('table');
    const row = document.createElement('tr');
    const cell = document.createElement('td');
    row.append(cell);
    table.append(row);
    scroller.append(table);
    document.body.append(scroller);
    Object.defineProperties(scroller, {
        clientWidth: { configurable: true, value: 400 },
        scrollWidth: { configurable: true, value: 1200 }
    });
    return { scroller, cell };
}

function wheelEvent(target, overrides = {}) {
    let prevented = false;
    let stopped = false;
    return {
        target,
        cancelable: true,
        deltaX: 120,
        deltaY: 0,
        deltaMode: 0,
        shiftKey: false,
        ctrlKey: false,
        preventDefault() {
            prevented = true;
        },
        stopPropagation() {
            stopped = true;
        },
        get prevented() {
            return prevented;
        },
        get stopped() {
            return stopped;
        },
        ...overrides
    };
}

test('horizontal wheel gestures scroll the Markdown table instead of the page', () => {
    const { document, host } = createHost();
    const { scroller, cell } = createScrollableTable(document);
    const event = wheelEvent(cell);

    assert.equal(host.handleAppWheel(event), true);
    assert.equal(scroller.scrollLeft, 120);
    assert.equal(event.prevented, true);
    assert.equal(event.stopped, true);
});

test('table edge still consumes horizontal gestures to block Safari navigation', () => {
    const { document, host } = createHost();
    const { scroller, cell } = createScrollableTable(document);
    scroller.scrollLeft = 800;
    const event = wheelEvent(cell);

    assert.equal(host.handleAppWheel(event), true);
    assert.equal(scroller.scrollLeft, 800);
    assert.equal(event.prevented, true);
    assert.equal(event.stopped, true);
});

test('left edge also consumes horizontal gestures without moving the table', () => {
    const { document, host } = createHost();
    const { scroller, cell } = createScrollableTable(document);
    const event = wheelEvent(cell, { deltaX: -120 });

    assert.equal(host.handleAppWheel(event), true);
    assert.equal(scroller.scrollLeft, 0);
    assert.equal(event.prevented, true);
    assert.equal(event.stopped, true);
});

test('negative, shifted, and line-mode gestures use the intended horizontal delta', () => {
    const { document, host } = createHost();
    const { scroller, cell } = createScrollableTable(document);
    scroller.scrollLeft = 400;

    assert.equal(
        host.handleAppWheel(
            wheelEvent(cell, { deltaX: -120 })
        ),
        true
    );
    assert.equal(scroller.scrollLeft, 280);

    assert.equal(
        host.handleAppWheel(
            wheelEvent(cell, {
                deltaX: 0,
                deltaY: 5,
                deltaMode: 1,
                shiftKey: true
            })
        ),
        true
    );
    assert.equal(scroller.scrollLeft, 360);
});

test('ordinary vertical wheel gestures remain available to the conversation', () => {
    const { document, host } = createHost();
    const { scroller, cell } = createScrollableTable(document);
    const event = wheelEvent(cell, {
        deltaX: 0,
        deltaY: 120
    });

    assert.equal(host.handleAppWheel(event), false);
    assert.equal(scroller.scrollLeft, 0);
    assert.equal(event.prevented, false);
    assert.equal(event.stopped, false);
});

test('vertical-dominant diagonals and pinch zoom remain unconsumed', () => {
    const { document, host } = createHost();
    const { scroller, cell } = createScrollableTable(document);
    const diagonal = wheelEvent(cell, {
        deltaX: 40,
        deltaY: 120
    });
    const zoom = wheelEvent(cell, {
        deltaX: 120,
        ctrlKey: true
    });

    assert.equal(host.handleAppWheel(diagonal), false);
    assert.equal(host.handleAppWheel(zoom), false);
    assert.equal(scroller.scrollLeft, 0);
    assert.equal(diagonal.prevented, false);
    assert.equal(zoom.prevented, false);
});

test('root horizontal gestures are consumed even outside a scrollable table', () => {
    const { document, host } = createHost();
    const outside = document.createElement('div');
    document.body.append(outside);
    const outsideEvent = wheelEvent(outside);
    assert.equal(host.handleAppWheel(outsideEvent), true);
    assert.equal(outsideEvent.prevented, true);
    assert.equal(outsideEvent.stopped, true);

    const { scroller, cell } = createScrollableTable(document);
    Object.defineProperty(scroller, 'scrollWidth', {
        configurable: true,
        value: 400
    });
    const fixedTableEvent = wheelEvent(cell);
    assert.equal(host.handleAppWheel(fixedTableEvent), true);
    assert.equal(fixedTableEvent.prevented, true);
});

test('root gestures preserve horizontal scrolling in ordinary overflow containers', () => {
    const { document, host } = createHost();
    const scroller = document.createElement('div');
    scroller.style.overflowX = 'auto';
    const child = document.createElement('span');
    scroller.append(child);
    document.body.append(scroller);
    Object.defineProperties(scroller, {
        clientWidth: { configurable: true, value: 300 },
        scrollWidth: { configurable: true, value: 900 }
    });
    const event = wheelEvent(child, { deltaX: 150 });

    assert.equal(host.handleAppWheel(event), true);
    assert.equal(scroller.scrollLeft, 150);
    assert.equal(event.prevented, true);
    assert.equal(event.stopped, true);
});

test('root does not process an event already handled by a child component', () => {
    const { document, host } = createHost();
    const target = document.createElement('div');
    document.body.append(target);
    const event = wheelEvent(target, { defaultPrevented: true });

    assert.equal(host.handleAppWheel(event), true);
    assert.equal(event.prevented, false);
    assert.equal(event.stopped, false);
});

test('the application installs one explicit non-passive root wheel guard', () => {
    const { document, host } = createHost();
    const target = document.createElement('div');
    document.body.append(target);
    const event = new document.defaultView.WheelEvent('wheel', {
        bubbles: true,
        cancelable: true,
        deltaX: 120,
        deltaY: 0
    });

    assert.equal(host.installRootWheelGuard(), true);
    assert.equal(host.installRootWheelGuard(), false);
    assert.equal(target.dispatchEvent(event), false);
    assert.equal(event.defaultPrevented, true);
});

test('the application root guard and CSS own horizontal containment', () => {
    assert.match(
        appSource,
        /document\.addEventListener\(\s*'wheel',[\s\S]*\{ passive: false \}/
    );
    assert.match(
        appSource,
        /async init\(\)[\s\S]*this\.installRootWheelGuard\(\)/
    );
    assert.doesNotMatch(
        appHtml,
        /@wheel=/
    );
    assert.match(
        appCss,
        /\.markdown-table-scroll\s*\{[^}]*overflow-x:\s*auto;/s
    );
    assert.match(
        appCss,
        /html\s*\{[^}]*overscroll-behavior-x:\s*none;/s
    );
    assert.match(
        appCss,
        /\.message-content \.markdown-table-scroll table\s*\{[^}]*width:\s*max-content;[^}]*min-width:\s*100%;/s
    );
    assert.match(
        appSource,
        /renderMarkdown\(content\)[\s\S]*renderMarkdown\(\s*content,\s*this\.lang\s*\)/
    );
    assert.match(
        pluginUiContract.horizontal_wheel.root_behavior,
        /across the ChatRaw page/
    );
    assert.match(
        pluginUiContract.horizontal_wheel.listener,
        /passive false/
    );
    assert.match(
        pluginUiContract.horizontal_wheel.scroll_target,
        /nearest ancestor.*overflow-x auto or scroll/
    );
    assert.equal(pluginUiContract.horizontal_wheel.ctrl_wheel_zoom, 'preserve');
});
