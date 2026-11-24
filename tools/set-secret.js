#!/usr/bin/env node
/*
 * Set a GitHub Actions repository secret without needing `gh`.
 *
 * Usage:
 *   GITHUB_TOKEN=... node tools/set-secret.js <owner>/<repo> <SECRET_NAME> <VALUE>
 *
 * Encryption follows GitHub's "sealed box" recipe:
 *   https://docs.github.com/en/rest/actions/secrets
 */
const fs = require('fs');
const path = require('path');
const nacl = require(process.env.TWEETNACL_PATH || path.join(__dirname, 'nacl-fast.js'));
const util = require(process.env.TWEETNACL_UTIL_PATH || path.join(__dirname, 'nacl-util.js'));
const { blake2b } = require(path.join(__dirname, 'blake2b.js'));

const [ownerRepo, name, value] = process.argv.slice(2);
const token = process.env.GITHUB_TOKEN;
if (!token || !ownerRepo || !name || value === undefined) {
  console.error('Usage: GITHUB_TOKEN=... node tools/set-secret.js <owner>/<repo> <NAME> <VALUE>');
  process.exit(2);
}
const [owner, repo] = ownerRepo.split('/');

async function api(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Authorization': `Bearer ${token}`,
      'Accept': 'application/vnd.github+json',
      'X-GitHub-Api-Version': '2022-11-28',
      ...(options.headers || {}),
    },
  });
  const text = await res.text();
  let body;
  try { body = JSON.parse(text); } catch { body = text; }
  if (!res.ok) throw new Error(`${res.status} ${url}: ${typeof body === 'string' ? body : JSON.stringify(body)}`);
  return body;
}

(async () => {
  const key = await api(`https://api.github.com/repos/${owner}/${repo}/actions/secrets/public-key`);
  const ephemeralKeyPair = nacl.box.keyPair();
  const recipientPublicKey = util.decodeBase64(key.key);
  // libsodium crypto_box_seal derives the nonce with BLAKE2b(ephemeral_pk || recipient_pk).
  const input = new Uint8Array(ephemeralKeyPair.publicKey.length + recipientPublicKey.length);
  input.set(ephemeralKeyPair.publicKey, 0);
  input.set(recipientPublicKey, ephemeralKeyPair.publicKey.length);
  // libsodium crypto_box_seal derives a 24-byte BLAKE2b nonce from epk || pk.
  const nonce = blake2b(input, null, 24);
  const msg = util.decodeUTF8(value);
  const boxed = nacl.box(msg, nonce, recipientPublicKey, ephemeralKeyPair.secretKey);
  const sealed = new Uint8Array(ephemeralKeyPair.publicKey.length + boxed.length);
  sealed.set(ephemeralKeyPair.publicKey, 0);
  sealed.set(boxed, ephemeralKeyPair.publicKey.length);

  await api(`https://api.github.com/repos/${owner}/${repo}/actions/secrets/${encodeURIComponent(name)}`, {
    method: 'PUT',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      encrypted_value: util.encodeBase64(sealed),
      key_id: key.key_id,
    }),
  });
  console.log(`Secret ${name} updated on ${ownerRepo}`);
})().catch(e => { console.error(e.message); process.exit(1); });
