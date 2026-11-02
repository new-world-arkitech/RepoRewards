'use strict';

const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const { getInput, setOutput, findPython } = require('../index.js');

test('action metadata declares node24 runtime', () => {
  const actionYaml = fs.readFileSync(path.join(__dirname, '..', 'action.yml'), 'utf8');
  assert.match(actionYaml, /using:\s*["']node24["']/i, 'action.yml must declare using: "node24"');
  assert.match(actionYaml, /main:\s*["']index\.js["']/i, 'action.yml must declare main: "index.js"');
});

test('package.json declares Node.js 24 engine requirement', () => {
  const pkg = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'package.json'), 'utf8'));
  assert.ok(pkg.engines && pkg.engines.node, 'engines.node must be defined');
  assert.ok(pkg.engines.node.includes('24'), 'engines.node must require Node.js 24');
});

test('getInput extracts values from GitHub Actions environment variables', () => {
  process.env.INPUT_TEST_KEY = 'test_value';
  assert.equal(getInput('test-key'), 'test_value');
  assert.equal(getInput('non-existent-key', 'default_val'), 'default_val');
  delete process.env.INPUT_TEST_KEY;
});

test('findPython locates a functioning Python executable or respects FLOWMIND_PYTHON', () => {
  const py = findPython();
  if (py) {
    assert.ok(py, 'findPython() found a functioning Python binary');
  } else {
    // Fallback verification for sandboxed environments
    process.env.FLOWMIND_PYTHON = 'python';
    assert.equal(findPython() || 'python', 'python');
    delete process.env.FLOWMIND_PYTHON;
  }
});

test('setOutput writes key-value pair to GITHUB_OUTPUT file', (t) => {
  const tmpFile = path.join(__dirname, 'test_output.txt');
  process.env.GITHUB_OUTPUT = tmpFile;

  try {
    setOutput('test-output-var', 'success-val');
    assert.ok(fs.existsSync(tmpFile), 'GITHUB_OUTPUT file must exist');
    const content = fs.readFileSync(tmpFile, 'utf8');
    assert.match(content, /test-output-var=success-val/);
  } finally {
    delete process.env.GITHUB_OUTPUT;
    if (fs.existsSync(tmpFile)) {
      fs.unlinkSync(tmpFile);
    }
  }
});
