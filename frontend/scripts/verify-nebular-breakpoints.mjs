import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { inspectNebularSass } from './apply-nebular-sass-fix.mjs';

const require = createRequire(import.meta.url);
const sass = require('sass');
const root = fileURLToPath(new URL('../', import.meta.url));
// The modern if(sass(...): ...; else: ...) syntax requires Dart Sass >= 1.95.0.
const version = sass.info.match(/dart-sass\s+(\d+)\.(\d+)\.(\d+)/);
assert.ok(version, 'Dart Sass is required');
assert.ok(Number(version[1]) > 1 || (Number(version[1]) === 1 && Number(version[2]) >= 95),
  'Nebular Sass patch requires Dart Sass >= 1.95.0');
const read = (relative) => readFileSync(path.join(root, relative), 'utf8');
assert.equal(JSON.parse(read('node_modules/@nebular/theme/package.json')).version, '17.0.0');
const breakpoints = read('node_modules/@nebular/theme/styles/global/_breakpoints.scss');
const typography = read('node_modules/@nebular/theme/styles/global/typography/_typography.scss');
const expressions = [
  'if(sass($min != 0): $min; else: null)',
  'if(sass($n < list.length($breakpoint-names)): list.nth($breakpoint-names, $n + 1); else: null)',
  'if(sass($next): breakpoint-min($next, $breakpoints) - 0.02px; else: null)',
  "if(sass(&): '&'; else: 'body')",
];
expressions.forEach((expression, index) => assert.ok(
  (index < 3 ? breakpoints : typography).includes(expression), `Missing patch expression: ${expression}`));
for (const file of inspectNebularSass(root)) assert.equal(file.source, file.corrected, 'Correction not applied');

const cases = [
  ['xs', 'null', 'is', '399.98px'], ['is', '400px', 'sm', '575.98px'],
  ['sm', '576px', 'md', '767.98px'], ['md', '768px', 'lg', '991.98px'],
  ['lg', '992px', 'xl', '1199.98px'], ['xl', '1200px', 'xxl', '1399.98px'],
  ['xxl', '1400px', 'xxxl', '1599.98px'], ['xxxl', '1600px', 'null', 'null'],
];
// No warning suppression: if-function is fatal; other warnings use Sass's default logger.
const options = { loadPaths: [path.join(root, 'node_modules')], fatalDeprecations: ['if-function'] };
const source = `@use 'sass:meta';\n${breakpoints}\n` + cases.map(([name, min, next, max]) => `
  @if breakpoint-min(${name}) != ${min} { @error 'Invalid minimum: ${name}'; }
  @if breakpoint-next(${name}) != ${next} { @error 'Invalid successor: ${name}'; }
  @if breakpoint-max(${name}) != ${max} { @error 'Invalid maximum: ${name}'; }
  @include media-breakpoint-up(${name}) { .up-${name} { display: block; } }
  @include media-breakpoint-down(${name}) { .down-${name} { display: block; } }
`).join('\n');
const css = sass.compileString(source, options).css;
for (const [name, min, , max] of cases) {
  for (const [direction, bound, comparison] of [['up', min, 'min'], ['down', max, 'max']]) {
    const rule = `.${direction}-${name} {\n  display: block;\n}`;
    assert.ok(css.includes(bound === 'null' ? rule :
      `@media (${comparison}-width: ${bound}) {\n  ${rule.replaceAll('\n', '\n  ')}\n}`),
    `Invalid media query: ${direction}-${name}`);
  }
}
// Cover the typography conditional in both selector contexts.
assert.equal(sass.compileString("#{if(sass(&): '&'; else: 'body')} { color: red; }", options).css,
  'body {\n  color: red;\n}');
assert.equal(sass.compileString(".theme { #{if(sass(&): '&'; else: 'body')} { color: red; } }", options).css,
  '.theme {\n  color: red;\n}');
const globalCss = sass.compile(path.join(root, 'src/styles.scss'), options).css;
const themes = [...new Set([...globalCss.matchAll(/\.nb-theme-([\w-]+)/g)].map((match) => match[1]))];
assert.deepEqual(themes, ['industrial-predict']);
for (const selector of ['nb-layout', 'nb-sidebar', 'nb-card']) assert.ok(globalCss.includes(selector));
if (process.argv[2]) {
  assert.equal(globalCss, readFileSync(path.resolve(process.argv[2]), 'utf8'), 'Global CSS changed');
  console.log('Global CSS is byte-for-byte identical to the supplied baseline.');
}
console.log(`Dart Sass ${version.slice(1).join('.')}: four patched expressions, eight breakpoints, media queries and single custom theme verified.`);
