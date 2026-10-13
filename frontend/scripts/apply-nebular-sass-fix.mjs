import { createHash } from 'node:crypto';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

// Nebular 17.0.0 only. Modern Sass if() requires Dart Sass >= 1.95.0.
// Keep this correction until an upstream release fixes these expressions.
export const corrections = [
  {
    file: 'styles/global/_breakpoints.scss',
    originalHash: '0176198e47ee389562ddfd8c0a90734b72d814a95b655e11eac16b92ecd007dc',
    replacements: [
      ['if($min != 0, $min, null)', 'if(sass($min != 0): $min; else: null)'],
      ['if($n < list.length($breakpoint-names), list.nth($breakpoint-names, $n + 1), null)',
        'if(sass($n < list.length($breakpoint-names)): list.nth($breakpoint-names, $n + 1); else: null)'],
      ['if($next, breakpoint-min($next, $breakpoints) - 0.02px, null)',
        'if(sass($next): breakpoint-min($next, $breakpoints) - 0.02px; else: null)'],
    ],
  },
  {
    file: 'styles/global/typography/_typography.scss',
    originalHash: 'ad21804203219b6d59f3c46d362883546e3e9d1bbe0c9e2bc2fb213557ac5cdd',
    replacements: [["if(&, '&', 'body')", "if(sass(&): '&'; else: 'body')"]],
  },
];
const root = fileURLToPath(new URL('../', import.meta.url));
const digest = (content) => createHash('sha256').update(content.replaceAll('\r\n', '\n')).digest('hex');
const count = (content, expression) => content.split(expression).length - 1;

export function inspectNebularSass(frontendRoot = root) {
  const nebular = path.join(frontendRoot, 'node_modules/@nebular/theme');
  const manifest = JSON.parse(readFileSync(path.join(nebular, 'package.json'), 'utf8'));
  if (manifest.version !== '17.0.0') throw new Error(`Expected Nebular 17.0.0; found ${manifest.version}`);
  return corrections.map(({ file, originalHash, replacements }) => {
    const filename = path.join(nebular, file);
    const source = readFileSync(filename, 'utf8');
    let original = source;
    let corrected = source;
    for (const [before, after] of replacements) {
      const beforeCount = count(source, before);
      const afterCount = count(source, after);
      if (beforeCount + afterCount !== 1) throw new Error(`Unexpected expression in ${file}: ${before}`);
      if (afterCount === 1) original = original.replace(after, before);
      if (beforeCount === 1) corrected = corrected.replace(before, after);
    }
    // Reject any unrelated change, even if all four expected expressions exist.
    if (digest(original) !== originalHash) throw new Error(`Unexpected source content in ${file}`);
    return { filename, source, corrected };
  });
}

export function applyNebularSassFix(frontendRoot = root) {
  // Validate BOTH files before writing either file.
  const files = inspectNebularSass(frontendRoot);
  let changed = 0;
  for (const { filename, source, corrected } of files) {
    if (source !== corrected) {
      writeFileSync(filename, corrected);
      changed += 1;
    }
  }
  return changed;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const changed = applyNebularSassFix();
    console.log(`Nebular 17.0.0 Sass correction: ${changed} files updated; four expressions verified (Dart Sass >= 1.95.0 required).`);
  } catch (error) {
    console.error(`Nebular Sass correction failed: ${error.message}`);
    process.exitCode = 1;
  }
}
