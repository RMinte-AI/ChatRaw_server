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
const cssSourcePath = 'backend/static/styles.css';
const cssOutputPath = 'backend/static/styles.min.css';

const jsSource = await fs.readFile(jsSourcePath, 'utf8');
const jsResult = await minify(jsSource, {
    compress: true,
    mangle: true
});
if (!jsResult.code) {
    throw new Error('Terser returned an empty JavaScript build');
}

const cssSource = await fs.readFile(cssSourcePath, 'utf8');
const cssResult = await postcss([cssnano]).process(cssSource, {
    from: cssSourcePath,
    to: cssOutputPath,
    map: { inline: true }
});

const outputs = [
    [jsOutputPath, jsResult.code],
    [cssOutputPath, cssResult.css]
];

if (mode === '--write') {
    for (const [outputPath, content] of outputs) {
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
