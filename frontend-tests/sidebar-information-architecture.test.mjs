import assert from 'node:assert/strict';
import fs from 'node:fs';
import test from 'node:test';

import { JSDOM } from 'jsdom';

const appHtml = fs.readFileSync('backend/static/index.html', 'utf8');
const appScript = fs.readFileSync('backend/static/app.js', 'utf8');
const appStyles = fs.readFileSync('backend/static/styles.css', 'utf8');

function createDocument() {
    const dom = new JSDOM(appHtml, {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
    });
    const style = dom.window.document.createElement('style');
    style.textContent = appStyles;
    dom.window.document.head.append(style);
    return dom;
}

test('sidebar feature entries precede chat creation and history', () => {
    const { window } = createDocument();
    const { document, Node } = window;
    const featureArea = document.querySelector('.sidebar-feature-area');
    const divider = document.querySelector('.sidebar-section-divider');
    const expandedNewChat = document.querySelector('.btn-new-chat');
    const collapsedNewChat = document.querySelector(
        '.btn-new-chat-collapsed'
    );
    const chatList = document.querySelector('.chat-list');

    const precedes = (left, right) => Boolean(
        left.compareDocumentPosition(right)
        & Node.DOCUMENT_POSITION_FOLLOWING
    );
    assert.equal(precedes(featureArea, divider), true);
    assert.equal(precedes(divider, expandedNewChat), true);
    assert.equal(precedes(divider, collapsedNewChat), true);
    assert.equal(precedes(expandedNewChat, chatList), true);
    assert.equal(precedes(collapsedNewChat, chatList), true);
});

test('feature visibility follows live sidebar registrations', () => {
    const dom = new JSDOM('<!doctype html><body></body>', {
        runScripts: 'outside-only',
        url: 'http://chatraw.test/'
    });
    dom.window.matchMedia = () => ({ matches: false });
    dom.window.marked = { setOptions() {} };
    dom.window.eval(appScript);
    const host = dom.window.app();

    assert.equal(host.hasSidebarFeatureEntries, false);
    host.pluginToolbarButtons = [{
        fullId: 'test-plugin:entry',
        pluginId: 'test-plugin',
        placement: 'sidebar'
    }];
    assert.equal(host.hasSidebarFeatureEntries, true);
    host.pluginToolbarButtons = [];
    assert.equal(host.hasSidebarFeatureEntries, false);

    host.residentIntegrations = [{
        feature: { visible: true },
        entrypoints: [{ id: 'entry', placement: 'sidebar', order: 10 }]
    }];
    assert.equal(host.hasSidebarFeatureEntries, true);
    host.residentIntegrations = [];
    assert.equal(host.hasSidebarFeatureEntries, false);
});

test('feature overflow preserves dedicated chat and footer space', () => {
    const { window } = createDocument();
    const { document } = window;
    const featureArea = document.querySelector('.sidebar-feature-area');
    featureArea.removeAttribute('x-cloak');

    const featureStyle = window.getComputedStyle(featureArea);
    const newChatStyle = window.getComputedStyle(
        document.querySelector('.btn-new-chat')
    );
    const chatListStyle = window.getComputedStyle(
        document.querySelector('.chat-list')
    );
    const footerStyle = window.getComputedStyle(
        document.querySelector('.sidebar-footer')
    );

    assert.equal(featureStyle.maxHeight, '40%');
    assert.equal(featureStyle.minHeight, '0');
    assert.equal(featureStyle.overflowY, 'auto');
    assert.equal(featureStyle.overscrollBehavior, 'contain');
    assert.equal(newChatStyle.flexShrink, '0');
    assert.equal(chatListStyle.minHeight, '48px');
    assert.equal(footerStyle.flexShrink, '0');
});
