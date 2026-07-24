import fs from 'node:fs/promises';
import path from 'node:path';
import { createHash } from 'node:crypto';
import { fileURLToPath } from 'node:url';

import cssnano from 'cssnano';
import postcss from 'postcss';
import { minify } from 'terser';

const scriptDir = path.dirname(fileURLToPath(import.meta.url));
const repoRoot = path.resolve(scriptDir, '..');
process.chdir(repoRoot);

const mode = process.argv[2];
if (!['--check', '--write'].includes(mode)) {
    console.error('Usage: node scripts/build-frontend.mjs --check|--write');
    process.exit(2);
}

const jsSourcePath = 'backend/static/app.js';
const jsOutputPath = 'backend/static/app.min.js';
const securitySourcePath = 'backend/static/content-security.js';
const securityOutputPath = 'backend/static/content-security.min.js';
const cssSourcePath = 'backend/static/styles.css';
const cssOutputPath = 'backend/static/styles.min.css';
const residentSourceRoot = 'ResidentIntegrations';
const residentOutputRoot = 'backend/static/resident-integrations';
const residentCatalogOutputPath = `${residentOutputRoot}/catalog.json`;
const residentJsOutputPath = `${residentOutputRoot}/resident-integrations.min.js`;
const residentCssOutputPath = `${residentOutputRoot}/resident-integrations.min.css`;
const vendorOutputs = [
    ['node_modules/marked/marked.min.js', 'backend/static/vendor/marked.min.js'],
    ['node_modules/dompurify/dist/purify.min.js', 'backend/static/vendor/purify.min.js'],
    ['node_modules/@alpinejs/collapse/dist/cdn.min.js', 'backend/static/vendor/alpine-collapse.min.js'],
    ['node_modules/alpinejs/dist/cdn.min.js', 'backend/static/vendor/alpine.min.js'],
    ['node_modules/@highlightjs/cdn-assets/highlight.min.js', 'backend/static/vendor/highlight/highlight.min.js'],
    ['node_modules/@highlightjs/cdn-assets/styles/github-dark.min.css', 'backend/static/vendor/highlight/github-dark.min.css'],
    ['node_modules/@highlightjs/cdn-assets/languages/python.min.js', 'backend/static/vendor/highlight/languages/python.min.js'],
    ['node_modules/@highlightjs/cdn-assets/languages/javascript.min.js', 'backend/static/vendor/highlight/languages/javascript.min.js'],
    ['node_modules/@highlightjs/cdn-assets/languages/bash.min.js', 'backend/static/vendor/highlight/languages/bash.min.js'],
    ['node_modules/@highlightjs/cdn-assets/languages/json.min.js', 'backend/static/vendor/highlight/languages/json.min.js'],
    ['node_modules/papaparse/papaparse.min.js', 'Plugins/Plugin_market/csv-parser/lib/papaparse.min.js']
];

async function loadResidentIntegrations() {
    const entries = await fs.readdir(residentSourceRoot, {
        withFileTypes: true
    });
    const directories = entries
        .filter(entry => entry.isDirectory())
        .map(entry => entry.name)
        .sort();
    const integrations = [];
    const ids = new Set();
    const javascript = [];
    const styles = [];
    for (const directory of directories) {
        const root = path.join(residentSourceRoot, directory);
        const descriptorPath = path.join(root, 'integration.json');
        const descriptor = JSON.parse(
            await fs.readFile(descriptorPath, 'utf8')
        );
        if (
            descriptor.schema_version !== '1'
            || typeof descriptor.id !== 'string'
            || descriptor.id !== directory
            || ids.has(descriptor.id)
            || typeof descriptor.main !== 'string'
            || typeof descriptor.styles !== 'string'
            || !Array.isArray(descriptor.entrypoints)
            || !Array.isArray(descriptor.required_actions)
        ) {
            throw new Error(
                `invalid resident integration descriptor: ${descriptorPath}`
            );
        }
        ids.add(descriptor.id);
        const entrypointIds = new Set();
        for (const entrypoint of descriptor.entrypoints) {
            if (
                !entrypoint
                || typeof entrypoint.id !== 'string'
                || entrypointIds.has(entrypoint.id)
            ) {
                throw new Error(
                    `duplicate resident entrypoint in ${descriptorPath}`
                );
            }
            entrypointIds.add(entrypoint.id);
        }
        for (const sourceFile of [descriptor.main, descriptor.styles]) {
            if (
                path.basename(sourceFile) !== sourceFile
                || sourceFile.includes('\\')
            ) {
                throw new Error(
                    `resident source must be a root filename: ${descriptorPath}`
                );
            }
        }
        const mainSource = await fs.readFile(
            path.join(root, descriptor.main),
            'utf8'
        );
        const styleSource = await fs.readFile(
            path.join(root, descriptor.styles),
            'utf8'
        );
        integrations.push(descriptor);
        javascript.push(
            `/* Resident Integration: ${descriptor.id} */\n${mainSource}`
        );
        styles.push(
            `/* Resident Integration: ${descriptor.id} */\n${styleSource}`
        );
    }
    const javascriptSource = javascript.join('\n');
    const styleSource = styles.join('\n');
    const bundleVersion = createHash('sha256')
        .update(JSON.stringify(integrations))
        .update('\0')
        .update(javascriptSource)
        .update('\0')
        .update(styleSource)
        .digest('hex');
    return {
        catalog: `${JSON.stringify({
            schema_version: '1',
            bundle_version: bundleVersion,
            integrations
        }, null, 2)}\n`,
        bundleVersion,
        javascript: javascriptSource,
        styles: styleSource
    };
}

const jsSource = await fs.readFile(jsSourcePath, 'utf8');
const jsResult = await minify(jsSource, {
    compress: true,
    mangle: true
});
if (!jsResult.code) {
    throw new Error('Terser returned an empty JavaScript build');
}
const securitySource = await fs.readFile(securitySourcePath, 'utf8');
const securityResult = await minify(securitySource, {
    compress: true,
    mangle: true
});
if (!securityResult.code) {
    throw new Error('Terser returned an empty content security build');
}

const cssSource = await fs.readFile(cssSourcePath, 'utf8');
const cssResult = await postcss([cssnano]).process(cssSource, {
    from: cssSourcePath,
    to: cssOutputPath,
    map: { inline: true }
});
const residentSources = await loadResidentIntegrations();
const residentJsResult = await minify(residentSources.javascript, {
    compress: true,
    mangle: true
});
if (!residentJsResult.code) {
    throw new Error('Terser returned an empty Resident Integration build');
}
const residentCssResult = await postcss([cssnano]).process(
    residentSources.styles,
    {
        from: residentSourceRoot,
        to: residentCssOutputPath,
        map: { inline: true }
    }
);

const outputs = [
    [jsOutputPath, jsResult.code],
    [securityOutputPath, securityResult.code],
    [cssOutputPath, cssResult.css],
    [residentCatalogOutputPath, residentSources.catalog],
    [residentJsOutputPath, residentJsResult.code],
    [residentCssOutputPath, residentCssResult.css]
];
for (const [sourcePath, outputPath] of vendorOutputs) {
    outputs.push([outputPath, await fs.readFile(sourcePath, 'utf8')]);
}

if (mode === '--write') {
    for (const [outputPath, content] of outputs) {
        await fs.mkdir(path.dirname(outputPath), { recursive: true });
        await fs.writeFile(outputPath, content);
        console.log(`built ${outputPath}`);
    }
    process.exit(0);
}

const drifted = [];
for (const [outputPath, expected] of outputs) {
    const actual = await fs.readFile(outputPath, 'utf8').catch(() => null);
    if (actual !== expected) {
        drifted.push(outputPath);
    }
}

if (drifted.length) {
    console.error(`frontend build drift detected: ${drifted.join(', ')}`);
    console.error('run: npm run build:frontend');
    process.exit(1);
}

console.log('frontend build artifacts match their source files');
