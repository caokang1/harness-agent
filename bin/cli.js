#!/usr/bin/env node
// ============================================================
// Harness Starter Kit · npm 入口（npx @your-org/harness-starter）
//
// 只做一件事：在当前目录（用户项目根）调用包内的 init.sh，参数原样透传。
//   npx @your-org/harness-starter --auto
//   npx @your-org/harness-starter --project-name=my-svc --modules=common,core,start
//
// 和 bootstrap.sh / install.sh 一样：模板从包目录复制到项目根，
// 项目根不会出现 .harness-starter/。
// ============================================================

'use strict';

const { spawnSync } = require('child_process');
const fs = require('fs');
const path = require('path');

const PKG_ROOT = path.resolve(__dirname, '..');
const INIT_SH = path.join(PKG_ROOT, 'init.sh');
const args = process.argv.slice(2);

if (args.includes('--version') || args.includes('-v')) {
  console.log(require(path.join(PKG_ROOT, 'package.json')).version);
  process.exit(0);
}

if (!fs.existsSync(INIT_SH)) {
  console.error(`[harness-starter] ❌ 包内容不完整：找不到 ${INIT_SH}`);
  process.exit(1);
}

// 找 bash：Linux / macOS 用 PATH 里的；Windows 优先 Git Bash（WSL 的 bash.exe 看不到 Windows 路径）
function findBash() {
  if (process.env.HARNESS_BASH) return process.env.HARNESS_BASH;
  if (process.platform !== 'win32') return 'bash';
  const roots = [
    process.env.ProgramFiles,
    process.env['ProgramFiles(x86)'],
    process.env.LOCALAPPDATA && path.join(process.env.LOCALAPPDATA, 'Programs'),
  ];
  for (const root of roots.filter(Boolean)) {
    const candidate = path.join(root, 'Git', 'bin', 'bash.exe');
    if (fs.existsSync(candidate)) return candidate;
  }
  // 装在其他位置（scoop、D 盘、便携版）的 Git：从 PATH 里找。
  // 跳过 System32 下的 bash.exe（那是 WSL 的入口，看不到 Windows 路径）
  const system32 = path.join(process.env.SystemRoot || 'C:\\Windows', 'System32').toLowerCase();
  for (const dir of (process.env.PATH || '').split(path.delimiter).filter(Boolean)) {
    if (path.resolve(dir).toLowerCase().startsWith(system32)) continue;
    const candidates = [
      path.join(dir, 'bash.exe'),
      path.join(dir, '..', 'bin', 'bash.exe'), // PATH 里通常是 <Git>\cmd，bash 在 <Git>\bin
    ];
    for (const candidate of candidates) {
      if (fs.existsSync(candidate)) return path.resolve(candidate);
    }
  }
  return null;
}

const bash = findBash();
if (!bash) {
  console.error('[harness-starter] ❌ 需要 bash 才能运行 init.sh。');
  console.error('  Windows：安装 Git for Windows（自带 Git Bash），或在 WSL 里运行本命令；');
  console.error('  也可以用环境变量 HARNESS_BASH 指定 bash 路径。');
  process.exit(127);
}

// Windows 下把路径交给 Git Bash 时用正斜杠，避免反斜杠被当成转义
const toBashPath = (p) => (process.platform === 'win32' ? p.replace(/\\/g, '/') : p);

const result = spawnSync(bash, [toBashPath(INIT_SH), ...args], {
  stdio: 'inherit',
  env: { ...process.env, HARNESS_TARGET_DIR: toBashPath(process.cwd()) },
});

if (result.error) {
  console.error(`[harness-starter] ❌ 无法启动 bash（${bash}）：${result.error.message}`);
  process.exit(127);
}
process.exit(result.status === null ? 1 : result.status);
