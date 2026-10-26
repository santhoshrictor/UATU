import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import test from 'node:test';
import { VOICE_CAPTURE_DEFAULTS } from '../lib/iris-audio.ts';
import { sameOrigin } from '../lib/local-origin.ts';

test('local voice capture reduces echo and background noise', () => {
  assert.equal(VOICE_CAPTURE_DEFAULTS.echoCancellation, true);
  assert.equal(VOICE_CAPTURE_DEFAULTS.noiseSuppression, true);
  assert.equal(VOICE_CAPTURE_DEFAULTS.autoGainControl, true);
  assert.equal(VOICE_CAPTURE_DEFAULTS.channelCount, 1);
});

test('origin guard permits loopback but rejects cross-site requests', () => {
  const request = (origin, host) =>
    new Request('http://localhost:3000/api/token', { headers: { Origin: origin, Host: host } });
  assert.equal(sameOrigin(request('http://127.0.0.1:3000', '127.0.0.1:3000')), true);
  assert.equal(sameOrigin(request('https://example.com', '127.0.0.1:3000')), false);
  assert.equal(sameOrigin(request('http://example.com', 'example.com')), false);
});

test('the app and token route no longer require admin credentials', async () => {
  const app = await readFile(new URL('../components/app/app.tsx', import.meta.url), 'utf8');
  const token = await readFile(new URL('../app/api/token/route.ts', import.meta.url), 'utf8');
  assert.equal(app.includes('IrisAccessGate'), false);
  assert.equal(token.includes('isAuthenticated'), false);
});

test(
  'local token requests work without login while cross-origin requests stay blocked',
  {
    skip: process.env.IRIS_HTTP_TESTS !== '1',
  },
  async () => {
    const origin = 'http://127.0.0.1:3000';
    let response = await fetch(`${origin}/api/token`, {
      method: 'POST',
      headers: { Origin: origin, 'Content-Type': 'application/json' },
      body: '{}',
    });
    assert.equal(response.status, 200);
    // Never print the returned voice token or provider connection values.
    response = await fetch(`${origin}/api/token`, {
      method: 'POST',
      headers: { Origin: 'https://example.com', 'Content-Type': 'application/json' },
      body: '{}',
    });
    assert.equal(response.status, 403);
    response = await fetch(`${origin}/api/auth`);
    assert.equal(response.status, 404);
  }
);
