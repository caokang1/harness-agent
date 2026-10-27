#!/usr/bin/env node
/**
 * render-graphs.js - render a skill's ```dot flowcharts to SVG so your human
 * partner can look at them.
 *
 * Usage:
 *   ./render-graphs.js ../some-skill            # Each diagram separately
 *   ./render-graphs.js ../some-skill --combine  # All diagrams in one SVG
 *
 * The argument is a skill directory (its SKILL.md is read) or a path to a
 * Markdown file. Every fenced ```dot (or ```graphviz / ```gv) block is
 * extracted and piped through the Graphviz `dot` CLI.
 *
 * Options:
 *   --combine         Write a single SVG with all diagrams stacked vertically
 *   --out-dir <dir>   Output directory (default: <skill-dir>/diagrams)
 *   --list            Only list the diagrams found; do not render
 *   -h, --help        Show this help
 *
 * Requires Graphviz (`dot` on PATH). No npm dependencies; Node 16+.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

const USAGE = `Usage: render-graphs.js <skill-dir | file.md> [--combine] [--out-dir <dir>] [--list]

Extracts \`\`\`dot code blocks from a skill's SKILL.md and renders them to SVG
with Graphviz.

  <skill-dir>       Skill directory containing SKILL.md (or a .md file path)
  --combine         Render all diagrams into one SVG (<skill>-all.svg)
  --out-dir <dir>   Where to write SVGs (default: <skill-dir>/diagrams)
  --list            List diagrams found without rendering
  -h, --help        Show this message

Examples:
  ./render-graphs.js ../some-skill
  ./render-graphs.js ../some-skill --combine
`;

function fail(msg, code = 1) {
  process.stderr.write(`render-graphs: ${msg}\n`);
  process.exit(code);
}

function parseArgs(argv) {
  const opts = { target: null, combine: false, outDir: null, list: false };
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i];
    if (a === '-h' || a === '--help') {
      process.stdout.write(USAGE);
      process.exit(0);
    } else if (a === '--combine') {
      opts.combine = true;
    } else if (a === '--list') {
      opts.list = true;
    } else if (a === '--out-dir' || a === '-o') {
      if (i + 1 >= argv.length) fail(`${a} requires a directory argument\n\n${USAGE}`);
      opts.outDir = argv[++i];
    } else if (a.startsWith('--out-dir=')) {
      opts.outDir = a.slice('--out-dir='.length);
    } else if (a.startsWith('-')) {
      fail(`unknown option: ${a}\n\n${USAGE}`);
    } else if (opts.target === null) {
      opts.target = a;
    } else {
      fail(`unexpected argument: ${a}\n\n${USAGE}`);
    }
  }
  if (!opts.target) {
    process.stderr.write(USAGE);
    process.exit(1);
  }
  return opts;
}

/** Resolve the CLI target to { mdFile, skillDir, skillName }. */
function resolveTarget(target) {
  const abs = path.resolve(target);
  if (!fs.existsSync(abs)) fail(`not found: ${target}`);
  if (fs.statSync(abs).isDirectory()) {
    const mdFile = path.join(abs, 'SKILL.md');
    if (!fs.existsSync(mdFile)) fail(`no SKILL.md in ${target}`);
    return { mdFile, skillDir: abs, skillName: path.basename(abs) };
  }
  const dir = path.dirname(abs);
  const base = path.basename(abs, path.extname(abs));
  return { mdFile: abs, skillDir: dir, skillName: base === 'SKILL' ? path.basename(dir) : base };
}

/** Extract all ```dot / ```graphviz / ```gv fenced blocks from Markdown text. */
function extractDotBlocks(markdown) {
  const text = markdown.replace(/\r\n/g, '\n');
  const blocks = [];
  const re = /^[ \t]*(`{3,}|~{3,})[ \t]*(?:dot|graphviz|gv)[ \t]*\n([\s\S]*?)^[ \t]*\1[ \t]*$/gim;
  let m;
  while ((m = re.exec(text)) !== null) {
    const source = m[2].replace(/\s+$/, '') + '\n';
    const line = text.slice(0, m.index).split('\n').length;
    const nameMatch = source.match(/^\s*(?:strict\s+)?(?:di)?graph\s+("(?:[^"\\]|\\.)*"|[A-Za-z0-9_]+)?/im);
    const name = nameMatch && nameMatch[1] ? nameMatch[1].replace(/^"|"$/g, '') : '';
    blocks.push({ name, source, line, fileName: '' });
  }
  // Give every block a unique, filesystem-safe name.
  const used = new Map();
  blocks.forEach((b, i) => {
    let safe = (b.name || `graph_${i + 1}`).replace(/[^A-Za-z0-9_.-]+/g, '_').replace(/^_+|_+$/g, '') || `graph_${i + 1}`;
    const n = used.get(safe) || 0;
    used.set(safe, n + 1);
    if (n > 0) safe = `${safe}_${n + 1}`;
    b.fileName = safe;
  });
  return blocks;
}

/** Run `dot -Tsvg` on the given source. Exits with a clear message if dot is missing. */
function renderSvg(source, label) {
  const res = spawnSync('dot', ['-Tsvg'], { input: source, encoding: 'utf8', maxBuffer: 64 * 1024 * 1024 });
  if (res.error) {
    if (res.error.code === 'ENOENT') {
      fail(
        'Graphviz `dot` command not found on PATH.\n' +
          'Install Graphviz first, e.g.:\n' +
          '  macOS:          brew install graphviz\n' +
          '  Debian/Ubuntu:  sudo apt-get install graphviz\n' +
          '  Windows:        winget install graphviz   (or: choco install graphviz)\n' +
          'Then re-run this script.'
      );
    }
    fail(`failed to run dot: ${res.error.message}`);
  }
  if (res.status !== 0) {
    return { ok: false, error: `dot failed for ${label}:\n${(res.stderr || '').trim()}` };
  }
  return { ok: true, svg: res.stdout };
}

/** Parse width/height (in pt) from an SVG produced by dot. */
function svgSize(svg) {
  const open = (svg.match(/<svg\b[^>]*>/) || [''])[0];
  const w = open.match(/\swidth="([\d.]+)/);
  const h = open.match(/\sheight="([\d.]+)/);
  return { width: w ? parseFloat(w[1]) : 0, height: h ? parseFloat(h[1]) : 0 };
}

function escapeXml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;').replace(/"/g, '&quot;');
}

/**
 * Stack individually rendered SVGs vertically into one document. Each diagram
 * is nested as its own <svg>, so node names in different diagrams never clash
 * (merging the dot sources into one graph would merge same-named nodes).
 */
function combineSvgs(rendered, title) {
  const gap = 30;
  const titleH = 24;
  let y = 10;
  let maxW = 0;
  const parts = [];
  for (const r of rendered) {
    const { width, height } = svgSize(r.svg);
    const inner = r.svg
      .replace(/<\?xml[\s\S]*?\?>/g, '')
      .replace(/<!DOCTYPE[^>]*>/gi, '')
      .replace(/<!--[\s\S]*?-->/g, '')
      .trim()
      // Outer viewBox uses 1 user unit = 1pt, so nested sizes must be unitless
      // (a nested "120pt" would be converted to 160 user units and overflow).
      .replace(/^<svg\b[^>]*>/, (tag) =>
        tag
          .replace(/\s(width|height)="[^"]*"/g, '')
          .replace(/^<svg\b/, `<svg x="10" y="${y + titleH}" width="${width}" height="${height}"`)
      );
    parts.push(
      `<text x="10" y="${y + 16}" font-family="Helvetica,Arial,sans-serif" font-size="14" font-weight="bold">${escapeXml(r.name)}</text>`,
      inner
    );
    y += titleH + height + gap;
    maxW = Math.max(maxW, width);
  }
  const totalW = Math.ceil(maxW + 20);
  const totalH = Math.ceil(y);
  return (
    `<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n` +
    `<svg xmlns="http://www.w3.org/2000/svg" xmlns:xlink="http://www.w3.org/1999/xlink" ` +
    `width="${totalW}pt" height="${totalH}pt" viewBox="0 0 ${totalW} ${totalH}">\n` +
    `<title>${escapeXml(title)}</title>\n` +
    `<rect width="100%" height="100%" fill="white"/>\n` +
    parts.join('\n') +
    `\n</svg>\n`
  );
}

function main() {
  const opts = parseArgs(process.argv.slice(2));
  const { mdFile, skillDir, skillName } = resolveTarget(opts.target);
  const blocks = extractDotBlocks(fs.readFileSync(mdFile, 'utf8'));

  if (blocks.length === 0) {
    console.log(`No \`\`\`dot blocks found in ${mdFile}`);
    return;
  }

  console.log(`Found ${blocks.length} diagram(s) in ${mdFile}`);
  if (opts.list) {
    blocks.forEach((b) => console.log(`  - ${b.fileName} (line ${b.line})`));
    return;
  }

  const outDir = path.resolve(opts.outDir || path.join(skillDir, 'diagrams'));

  const rendered = [];
  let failures = 0;
  for (const b of blocks) {
    const r = renderSvg(b.source, `${b.fileName} (line ${b.line})`);
    if (!r.ok) {
      process.stderr.write(r.error + '\n');
      failures++;
      continue;
    }
    rendered.push({ name: b.fileName, svg: r.svg });
    if (!opts.combine) {
      fs.mkdirSync(outDir, { recursive: true });
      const out = path.join(outDir, `${b.fileName}.svg`);
      fs.writeFileSync(out, r.svg);
      console.log(`  wrote ${out}`);
    }
  }

  if (opts.combine && rendered.length > 0) {
    fs.mkdirSync(outDir, { recursive: true });
    const out = path.join(outDir, `${skillName}-all.svg`);
    fs.writeFileSync(out, combineSvgs(rendered, skillName));
    console.log(`  wrote ${out} (${rendered.length} diagram(s))`);
  }

  if (failures > 0) {
    process.stderr.write(`${failures} diagram(s) failed to render\n`);
    process.exit(1);
  }
}

if (require.main === module) {
  main();
}

module.exports = { extractDotBlocks, combineSvgs };
