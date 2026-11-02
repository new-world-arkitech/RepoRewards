#!/usr/bin/env node
/**
 * FlowMind GitHub Action Entrypoint
 * Runtime: Node.js 24 (node24)
 * Author: Cosmic Souls Of Sovereignty Inc. (@new-world-arkitech)
 * License: MIT
 *
 * Implements GitHub Actions Node.js 24 runner integration for autonomous
 * multi-agent architectural invariant audits, flow archaeology, and PR reviews.
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { spawnSync } = require('child_process');

function getInput(name, defaultValue = '') {
  const val =
    process.env[`INPUT_${name.replace(/ /g, '_').toUpperCase()}`] ??
    process.env[`INPUT_${name.replace(/[- ]/g, '_').toUpperCase()}`] ??
    defaultValue;
  return typeof val === 'string' ? val.trim() : defaultValue;
}

function setOutput(name, value) {
  const outputPath = process.env.GITHUB_OUTPUT;
  if (outputPath) {
    fs.appendFileSync(outputPath, `${name}=${value}\n`, 'utf8');
  }
}

function setSummary(markdown) {
  const summaryPath = process.env.GITHUB_STEP_SUMMARY;
  if (summaryPath) {
    fs.appendFileSync(summaryPath, markdown + '\n', 'utf8');
  }
}

function logError(message) {
  console.error(`::error::${message}`);
}

function logNotice(message) {
  console.log(`::notice::${message}`);
}

function findPython() {
  const custom = process.env.FLOWMIND_PYTHON || process.env.PYTHON;
  const candidates = [];
  if (custom) candidates.push(custom);

  if (process.platform === 'win32') {
    candidates.push('python', 'py', 'python3');
    const localAppData = process.env.LOCALAPPDATA || '';
    if (localAppData) {
      candidates.push(
        path.join(localAppData, 'Python', 'pythoncore-3.14-64', 'python.exe'),
        path.join(localAppData, 'Programs', 'Python', 'Python312', 'python.exe'),
        path.join(localAppData, 'Programs', 'Python', 'Python311', 'python.exe')
      );
    }
    // GitHub Actions Windows Runner Toolcache
    candidates.push(
      'C:\\hostedtoolcache\\windows\\Python\\3.12.0\\x64\\python.exe',
      'C:\\hostedtoolcache\\windows\\Python\\3.11.0\\x64\\python.exe'
    );
  } else {
    candidates.push(
      'python3',
      'python',
      '/opt/hostedtoolcache/Python/3.12.0/x64/bin/python3',
      '/opt/hostedtoolcache/Python/3.11.0/x64/bin/python3'
    );
  }

  for (const cmd of candidates) {
    try {
      const res = spawnSync(cmd, ['--version'], { encoding: 'utf8', timeout: 5000 });
      if (res.status === 0 && (res.stdout || res.stderr)) {
        return cmd;
      }
    } catch {
      // Try next candidate
    }
  }
  return null;
}

function run() {
  console.log('------------------------------------------------------------');
  console.log('🧠 FlowMind Architectural Invariant Audit & A2A Reviewer');
  console.log(`⚡ Action Runtime: Node.js ${process.version} (Target: node24)`);
  console.log('🏛️ Published by Cosmic Souls Of Sovereignty Inc. (@new-world-arkitech)');
  console.log('------------------------------------------------------------\n');

  // 1. Parse action inputs
  const repoPath = getInput('repo-path', '.');
  const tier = getInput('tier', 'auto');
  const dryRun = getInput('dry-run', 'true').toLowerCase() === 'true';
  const reportHtml = getInput('report-html', 'flowmind-report.html');
  const postPrComment = getInput('post-pr-comment', 'true').toLowerCase() === 'true';
  const failOnGates = getInput('fail-on-gates', 'true').toLowerCase() === 'true';
  const githubToken = getInput('github-token', process.env.GITHUB_TOKEN || '');

  // 2. Discover Python runtime
  const pythonCmd = findPython();
  if (!pythonCmd) {
    logError('Python 3.10+ runtime not found in runner environment. Please ensure actions/setup-python is run or Python is installed.');
    process.exit(1);
  }

  const pyVer = spawnSync(pythonCmd, ['--version'], { encoding: 'utf8' }).stdout.trim();
  console.log(`[FlowMind Engine] Detected host Python: ${pyVer} (using binary: ${pythonCmd})`);

  // 3. Ensure FlowMind package is installed in environment
  const actionRoot = __dirname;
  console.log(`[FlowMind Engine] Installing / verifying FlowMind package from: ${actionRoot}`);
  const installRes = spawnSync(
    pythonCmd,
    ['-m', 'pip', 'install', '--quiet', actionRoot],
    { stdio: 'inherit', env: process.env }
  );

  if (installRes.status !== 0) {
    logNotice('Could not pip install action directory, falling back to direct PYTHONPATH execution.');
  }

  // 4. Build command line arguments for FlowMind CLI
  const args = [
    '-m', 'repo_investigator.cli',
    repoPath,
    '--tier', tier,
    '--report-html', reportHtml,
  ];

  if (dryRun) args.push('--dry-run');
  if (postPrComment) args.push('--post-pr-comment');
  if (failOnGates) args.push('--fail-on-gates');

  console.log(`[FlowMind Execution] Spawning: ${pythonCmd} ${args.join(' ')}\n`);

  // 5. Execute FlowMind Invariant Audit
  const env = {
    ...process.env,
    PYTHONPATH: actionRoot + (process.env.PYTHONPATH ? path.delimiter + process.env.PYTHONPATH : ''),
  };
  if (githubToken) {
    env.GITHUB_TOKEN = githubToken;
  }

  const child = spawnSync(pythonCmd, args, {
    stdio: 'inherit',
    env: env,
  });

  const exitCode = child.status ?? (child.signal ? 1 : 0);

  // 6. Set Outputs & Step Summary
  setOutput('report-path', reportHtml);

  if (fs.existsSync(reportHtml)) {
    const stats = fs.statSync(reportHtml);
    console.log(`\n[OK] Generated Client-Facing Interactive HTML Report: ${reportHtml} (${stats.size} bytes)`);
    setSummary(`### 🧠 FlowMind Architectural Audit Complete\n- **Execution Status**: ${exitCode === 0 ? '✅ PASSED' : '❌ FAILED'}\n- **Report Generated**: \`${reportHtml}\`\n- **Node Runtime**: \`${process.version}\`\n\n*Review full details in the uploaded artifact and PR comments.*`);
  }

  if (exitCode !== 0) {
    logError(`FlowMind verification gates or execution failed with exit code ${exitCode}.`);
    process.exit(exitCode);
  }

  console.log('\n[SUCCESS] FlowMind Node.js 24 Action completed successfully.');
}

if (require.main === module) {
  run();
}

module.exports = {
  getInput,
  setOutput,
  findPython,
  run,
};
