import assert from 'node:assert/strict';
import { mkdtempSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import test from 'node:test';
import { applyNebularSassFix, corrections } from './apply-nebular-sass-fix.mjs';

const installed = fileURLToPath(new URL('../node_modules/@nebular/theme/', import.meta.url));
function fixture(t) {
  const prefix = path.join(tmpdir(), 'nebular-sass-test-');
  const root = mkdtempSync(prefix);
  t.after(() => {
    assert.ok(path.resolve(root).startsWith(path.resolve(prefix)));
    rmSync(root, { recursive: true, force: false });
  });
  const vendor = path.join(root, 'node_modules/@nebular/theme');
  mkdirSync(vendor, { recursive: true });
  writeFileSync(path.join(vendor, 'package.json'), JSON.stringify({ version: '17.0.0' }));
  const files = corrections.map(({ file, replacements }) => {
    let original = readFileSync(path.join(installed, file), 'utf8');
    for (const [before, after] of replacements) original = original.replace(after, before);
    const filename = path.join(vendor, file);
    mkdirSync(path.dirname(filename), { recursive: true });
    writeFileSync(filename, original);
    return { filename, original, replacements };
  });
  return { root, vendor, files };
}

test('changes only the four expressions and is idempotent', (t) => {
  const { root, files } = fixture(t);
  assert.equal(applyNebularSassFix(root), 2);
  for (const { filename, original, replacements } of files) {
    let expected = original;
    for (const [before, after] of replacements) expected = expected.replace(before, after);
    assert.equal(readFileSync(filename, 'utf8'), expected);
  }
  assert.equal(applyNebularSassFix(root), 0);
});

test('rejects a different Nebular version before writing', (t) => {
  const { root, vendor, files } = fixture(t);
  writeFileSync(path.join(vendor, 'package.json'), '{"version":"17.0.1"}');
  assert.throws(() => applyNebularSassFix(root), /Expected Nebular 17.0.0/);
  assert.equal(readFileSync(files[0].filename, 'utf8'), files[0].original);
});

test('rejects an unexpected expression in the second file before changing the first', (t) => {
  const { root, files } = fixture(t);
  writeFileSync(files[1].filename, files[1].original.replace("if(&, '&', 'body')", "if(&, '&', 'main')"));
  assert.throws(() => applyNebularSassFix(root), /Unexpected expression/);
  assert.equal(readFileSync(files[0].filename, 'utf8'), files[0].original);
});

test('rejects unrelated source changes', (t) => {
  const { root, files } = fixture(t);
  writeFileSync(files[1].filename, files[1].original + '\n// unexpected change\n');
  assert.throws(() => applyNebularSassFix(root), /Unexpected source content/);
  assert.equal(readFileSync(files[0].filename, 'utf8'), files[0].original);
});

test('rejects missing files before writing', (t) => {
  const { root, files } = fixture(t);
  rmSync(files[1].filename);
  assert.throws(() => applyNebularSassFix(root), /ENOENT/);
  assert.equal(readFileSync(files[0].filename, 'utf8'), files[0].original);
});
