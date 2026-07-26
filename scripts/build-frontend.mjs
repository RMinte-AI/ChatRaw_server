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
const staticRootPath = 'backend/static';
const htmlEntrypoints = [
    {
        outputPath: 'backend/static/index.html',
        assetPaths: [
            'styles.min.css',
            'app.min.js',
            'content-security.min.js',
            'vendor/marked.min.js',
            'vendor/purify.min.js',
            'vendor/alpine-collapse.min.js',
            'vendor/alpine.min.js'
        ]
    },
    {
        outputPath: 'backend/static/login.html',
        assetPaths: ['auth.css', 'auth.js']
    },
    {
        outputPath: 'backend/static/setup.html',
        assetPaths: ['auth.css', 'auth.js']
    }
];
const assetManifestOutputPath = 'backend/static/frontend-assets.json';
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
function sha256(content) {
    return createHash('sha256').update(content).digest('hex');
}

function staticRelativePath(outputPath) {
    const prefix = 'backend/static/';
    return outputPath.startsWith(prefix)
        ? outputPath.slice(prefix.length)
        : null;
}

function rewriteAssetVersions(html, versions, assetPaths) {
    let rewritten = html;
    for (const assetPath of assetPaths) {
        const version = versions[assetPath];
        if (!version) {
            throw new Error(`missing frontend asset version: ${assetPath}`);
        }
        const escaped = assetPath.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        rewritten = rewritten.replace(
            new RegExp(
                `((?:href|src)=["'])(/?)${escaped}(?:\\?v=[^"']+)?(["'])`,
                'g'
            ),
            `$1$2${assetPath}?v=${version}$3`
        );
    }
    return rewritten;
}

async function loadStaticAssetContents(
    directory = staticRootPath,
    relativeDirectory = ''
) {
    const contents = new Map();
    const entries = await fs.readdir(directory, { withFileTypes: true });
    for (const entry of entries) {
        const relativePath = path.posix.join(relativeDirectory, entry.name);
        const absolutePath = path.join(directory, entry.name);
        if (entry.isDirectory()) {
            const nested = await loadStaticAssetContents(
                absolutePath,
                relativePath
            );
            for (const item of nested) contents.set(...item);
        } else if (
            entry.isFile()
            && relativePath !== path.basename(assetManifestOutputPath)
        ) {
            contents.set(relativePath, await fs.readFile(absolutePath));
        }
    }
    return contents;
}

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

const assetContents = await loadStaticAssetContents();
for (const [outputPath, content] of outputs) {
    const relativePath = staticRelativePath(outputPath);
    if (relativePath) assetContents.set(relativePath, content);
}

const assetVersions = Object.fromEntries(
    [...assetContents.entries()]
        .map(([assetPath, content]) => [assetPath, sha256(content)])
        .sort(([left], [right]) => left.localeCompare(right))
);
assetVersions['resident-integrations/resident-integrations.min.js']
    = residentSources.bundleVersion;
assetVersions['resident-integrations/resident-integrations.min.css']
    = residentSources.bundleVersion;

const renderedEntrypoints = [];
for (const entrypoint of htmlEntrypoints) {
    const source = await fs.readFile(entrypoint.outputPath, 'utf8');
    const rendered = rewriteAssetVersions(
        source,
        assetVersions,
        entrypoint.assetPaths
    );
    const relativePath = staticRelativePath(entrypoint.outputPath);
    assetContents.set(relativePath, rendered);
    assetVersions[relativePath] = sha256(rendered);
    renderedEntrypoints.push({
        ...entrypoint,
        source,
        rendered
    });
}

const assetManifest = `${JSON.stringify({
    schema_version: '1',
    entrypoint: 'index.html',
    assets: Object.fromEntries(
        [...assetContents.entries()]
            .sort(([left], [right]) => left.localeCompare(right))
            .map(([assetPath, content]) => [
                assetPath,
                {
                    sha256: sha256(content),
                    version: assetVersions[assetPath]
                }
            ])
    )
}, null, 2)}\n`;

if (mode === '--write') {
    for (const entrypoint of renderedEntrypoints) {
        await fs.writeFile(entrypoint.outputPath, entrypoint.rendered);
    }
    for (const [outputPath, content] of outputs) {
        await fs.mkdir(path.dirname(outputPath), { recursive: true });
        await fs.writeFile(outputPath, content);
        console.log(`built ${outputPath}`);
    }
    await fs.writeFile(assetManifestOutputPath, assetManifest);
    console.log(`built ${assetManifestOutputPath}`);
    process.exit(0);
}

const drifted = [];
for (const entrypoint of renderedEntrypoints) {
    if (entrypoint.source !== entrypoint.rendered) {
        drifted.push(entrypoint.outputPath);
    }
}
for (const [outputPath, expected] of outputs) {
    const actual = await fs.readFile(outputPath, 'utf8').catch(() => null);
    if (actual !== expected) {
        drifted.push(outputPath);
    }
}
const actualManifest = await fs.readFile(
    assetManifestOutputPath,
    'utf8'
).catch(() => null);
if (actualManifest !== assetManifest) {
    drifted.push(assetManifestOutputPath);
}

if (drifted.length) {
    console.error(`frontend build drift detected: ${drifted.join(', ')}`);
    console.error('run: npm run build:frontend');
    process.exit(1);
}

console.log('frontend build artifacts match their source files');
