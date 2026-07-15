import assert from 'node:assert/strict';
import { test } from 'node:test';

import { deriveSeed } from './derive.mjs';

test('deriveSeed is a 64-char hex string', () => {
  const seed = deriveSeed('learner');
  assert.match(seed, /^[0-9a-f]{64}$/);
});

test('deriveSeed is deterministic (same label -> same seed)', () => {
  assert.equal(deriveSeed('learner'), deriveSeed('learner'));
});

test('deriveSeed differs by label (organization != learner)', () => {
  assert.notEqual(deriveSeed('organization'), deriveSeed('learner'));
});
