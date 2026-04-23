#!/usr/bin/env node
// ==============================================================================
// MAKRAY — Environment Doctor
// ==============================================================================
// Checks that all required tools and configuration are present.
// Run with: node scripts/doctor.js  (or: npm run doctor)
// Exit code 0 = all checks passed, 1 = one or more required checks failed.
// ==============================================================================

'use strict';

const { execSync } = require('child_process');
const fs = require('fs');
const path = require('path');

// ---------------------------------------------------------------------------
// Colour helpers (no external dependencies)
// ---------------------------------------------------------------------------
const c = {
  reset: '\x1b[0m',
  bold: '\x1b[1m',
  green: '\x1b[32m',
  red: '\x1b[31m',
  yellow: '\x1b[33m',
  cyan: '\x1b[36m',
  gray: '\x1b[90m',
};

const pass = `${c.green}✓ PASS${c.reset}`;
const fail = `${c.red}✗ FAIL${c.reset}`;
const warn = `${c.yellow}⚠ WARN${c.reset}`;

function label(text) {
  return `${c.cyan}${text.padEnd(28)}${c.reset}`;
}

// ---------------------------------------------------------------------------
// Helper utilities
// ---------------------------------------------------------------------------

/** Run a shell command and return stdout, or null on error. */
function run(cmd) {
  try {
    return execSync(cmd, { stdio: ['pipe', 'pipe', 'pipe'] })
      .toString()
      .trim();
  } catch {
    return null;
  }
}

/** Parse a semver string and return [major, minor, patch] as numbers. */
function parseSemver(version) {
  const match = (version || '').replace(/^v/, '').match(/^(\d+)\.(\d+)\.(\d+)/);
  if (!match) return null;
  return [parseInt(match[1], 10), parseInt(match[2], 10), parseInt(match[3], 10)];
}

/** Compare two [major, minor, patch] tuples. Returns true if actual >= required. */
function semverGte(actual, required) {
  if (!actual) return false;
  for (let i = 0; i < 3; i++) {
    if (actual[i] > required[i]) return true;
    if (actual[i] < required[i]) return false;
  }
  return true; // equal
}

// ---------------------------------------------------------------------------
// Checks
// ---------------------------------------------------------------------------
const results = [];
let anyRequiredFailed = false;

/**
 * @param {string} name       Display name
 * @param {boolean} ok        Did the check pass?
 * @param {string} detail     Extra detail to show
 * @param {boolean} required  If false, failure is a warning, not a hard fail
 */
function check(name, ok, detail = '', required = true) {
  const icon = ok ? pass : required ? fail : warn;
  const detailStr = detail ? ` ${c.gray}(${detail})${c.reset}` : '';
  console.log(`  ${label(name)} ${icon}${detailStr}`);
  results.push({ name, ok, required });
  if (!ok && required) anyRequiredFailed = true;
}

// ---------------------------------------------------------------------------
// Run all checks
// ---------------------------------------------------------------------------
console.log();
console.log(`${c.bold}MAKRAY — environment diagnostic${c.reset}`);
console.log(`${'='.repeat(50)}`);
console.log();

// --- Node.js version ---
const nodeRaw = run('node --version');
const nodeParsed = parseSemver(nodeRaw);
check(
  'Node.js >= 20',
  semverGte(nodeParsed, [20, 0, 0]),
  nodeRaw || 'not found',
  true
);

// --- npm version ---
const npmRaw = run('npm --version');
const npmParsed = parseSemver(npmRaw);
check(
  'npm >= 10',
  semverGte(npmParsed, [10, 0, 0]),
  npmRaw ? `v${npmRaw}` : 'not found',
  true
);

// --- Git ---
const gitRaw = run('git --version');
check(
  'Git',
  gitRaw !== null,
  gitRaw || 'not found',
  true
);

// --- TypeScript (via npx) ---
const tscRaw = run('npx tsc --version 2>/dev/null');
check(
  'TypeScript (npx tsc)',
  tscRaw !== null && tscRaw.startsWith('Version'),
  tscRaw || 'not found',
  false // optional until node_modules are installed
);

// --- .env file ---
const envPath = path.resolve(__dirname, '..', '.env');
const envExists = fs.existsSync(envPath);
check(
  '.env file',
  envExists,
  envExists ? envPath : "run 'make env' or 'npm run setup'",
  true
);

// --- node_modules ---
const nmPath = path.resolve(__dirname, '..', 'node_modules');
const nmExists = fs.existsSync(nmPath);
check(
  'node_modules',
  nmExists,
  nmExists ? 'present' : "run 'npm install'",
  true
);

// --- ANTHROPIC_API_KEY ---
// Load .env manually (no dotenv dependency)
let envVars = {};
if (envExists) {
  const raw = fs.readFileSync(envPath, 'utf8');
  for (const line of raw.split('\n')) {
    const trimmed = line.trim();
    if (!trimmed || trimmed.startsWith('#')) continue;
    const eqIdx = trimmed.indexOf('=');
    if (eqIdx === -1) continue;
    const key = trimmed.slice(0, eqIdx).trim();
    const val = trimmed.slice(eqIdx + 1).trim().replace(/^["']|["']$/g, '');
    envVars[key] = val;
  }
}

const apiKey = process.env.ANTHROPIC_API_KEY || envVars['ANTHROPIC_API_KEY'] || '';
const apiKeySet =
  apiKey.length > 0 &&
  apiKey !== 'your_anthropic_api_key_here';
check(
  'ANTHROPIC_API_KEY',
  apiKeySet,
  apiKeySet ? 'set' : 'not set or still placeholder',
  true
);

// --- MAKRAY_VAULT ---
const vaultVal = process.env.MAKRAY_VAULT || envVars['MAKRAY_VAULT'] || '';
const vaultSet =
  vaultVal.length > 0 &&
  vaultVal !== '/path/to/your/obsidian/vault';
const vaultExists = vaultSet && fs.existsSync(vaultVal);

check(
  'MAKRAY_VAULT set',
  vaultSet,
  vaultSet ? vaultVal : 'not set or still placeholder',
  true
);
check(
  'MAKRAY_VAULT path exists',
  vaultExists,
  vaultExists ? 'found' : vaultSet ? `path not found: ${vaultVal}` : 'skipped',
  true
);

// ---------------------------------------------------------------------------
// Summary
// ---------------------------------------------------------------------------
console.log();
console.log('='.repeat(50));
const passed = results.filter((r) => r.ok).length;
const total = results.length;

if (anyRequiredFailed) {
  console.log(
    `\n${c.red}${c.bold}${passed}/${total} checks passed — fix the failures above before proceeding.${c.reset}\n`
  );
  process.exit(1);
} else {
  console.log(
    `\n${c.green}${c.bold}${passed}/${total} checks passed — environment looks good!${c.reset}\n`
  );
  process.exit(0);
}
