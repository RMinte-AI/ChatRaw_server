import fs from 'node:fs/promises';
import path from 'node:path';
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

const outputs = [
    [jsOutputPath, jsResult.code],
    [securityOutputPath, securityResult.code],
    [cssOutputPath, cssResult.css]
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
