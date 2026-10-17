import assert from 'node:assert/strict';
import { after, afterEach, before, beforeEach, test } from 'node:test';
import { mkdtemp, mkdir, rm, writeFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import path from 'node:path';
import { createSitesSimulation, simulationCsp, simulationHeader } from './sites-simulation-server.mjs';

let root, server, origin;
before(async () => {
  root = await mkdtemp(path.join(tmpdir(), 'ipa-sites-simulation-'));
  await writeFile(path.join(root, 'index.html'), `<html><link rel="stylesheet" href="styles.css" media="print" onload="this.media='all'"><body><app-root></app-root><script src="main.js"></script></body></html>`);
  await writeFile(path.join(root, 'main.js'), '/* fixture */');
  await mkdir(path.join(root, 'assets'));
});
after(async () => {
  assert.equal(path.dirname(path.resolve(root)), path.resolve(tmpdir()));
  assert.match(path.basename(root), /^ipa-sites-simulation-/);
  await rm(root, { recursive: true, force: true });
});
beforeEach(async () => {
  server = await createSitesSimulation(root);
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  origin = `http://127.0.0.1:${server.address().port}`;
});
afterEach(async () => {
  server.closeAllConnections();
  await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
});
async function session() {
  const response = await fetch(origin + '/sites/new');
  const cookie = response.headers.get('set-cookie').split(';')[0];
  return { 'Content-Type': 'application/json', Origin: origin, Cookie: cookie };
}
const createBody = { company_id: 9001, name: 'Site de démonstration', code: 'DEMO-SITE-001' };

test('identifies isolation, injects an explicit banner and restricts browser network/form targets to self', async () => {
  const response = await fetch(origin + '/sites/new');
  assert.equal(response.headers.get('x-industrial-predict-simulation'), simulationHeader);
  assert.equal(response.headers.get('content-security-policy'), simulationCsp);
  assert.match(simulationCsp, /connect-src 'self'; form-action 'self'/);
  const html = await response.text();
  assert.match(html, /SIMULATION ISOLEE/);
  assert.match(html, /<link rel="stylesheet" href="styles.css">/);
  assert.doesNotMatch(html, /onload=|media="print"/);
  assert.match(response.headers.get('set-cookie'), /HttpOnly; SameSite=Strict/);
  const status = await (await fetch(origin + '/__simulation/status')).json();
  assert.equal(status.upstream, null); assert.equal(status.persistence, 'memory-only');
  assert.equal(response.headers.get('access-control-allow-origin'), null);
});
test('simulates POST, GET and differential PATCH in memory, retaining exact code and journal bodies', async () => {
  const headers = await session();
  const createdResponse = await fetch(origin + '/api/v1/sites', { method: 'POST', headers, body: JSON.stringify(createBody) });
  assert.equal(createdResponse.status, 201);
  const created = await createdResponse.json(); assert.equal(created.code, 'DEMO-SITE-001'); assert.equal(created.id, 9002);
  const body = { name: 'Site de démonstration - Modifié', description: 'Description mise à jour.' };
  const response = await fetch(origin + `/api/v1/sites/${created.id}`, { method: 'PATCH', headers, body: JSON.stringify(body) });
  assert.equal(response.status, 200);
  const updated = await response.json(); assert.equal(updated.code, created.code); assert.equal(updated.company_id, 9001);
  assert.equal(updated.description, body.description);
  assert.deepEqual(await (await fetch(origin + `/api/v1/sites/${created.id}`)).json(), updated);
  assert.deepEqual(await (await fetch(origin + '/__simulation/journal')).json(), [
    { method: 'POST', path: '/api/v1/sites', body: createBody }, { method: 'PATCH', path: '/api/v1/sites/9002', body }
  ]);
});
test('blocks submissions without a verified session or with another origin, with no simulated mutation', async () => {
  const headers = await session();
  for (const candidate of [ { ...headers, Cookie: '' }, { ...headers, Origin: 'http://127.0.0.1:8000' }, { ...headers, Origin: '' } ]) {
    const response = await fetch(origin + '/api/v1/sites', { method: 'POST', headers: candidate, body: JSON.stringify(createBody) });
    assert.equal(response.status, 503);
  }
  assert.deepEqual(await (await fetch(origin + '/__simulation/journal')).json(), []);
  assert.equal((await (await fetch(origin + '/api/v1/sites')).json()).total, 1);
});
test('rejects unknown write routes, DELETE, PUT and missing real identifiers instead of forwarding', async () => {
  const headers = await session();
  for (const [method, route] of [['POST', '/api/v1/companies'], ['PATCH', '/api/v1/sites/3/edit'], ['DELETE', '/api/v1/sites/3'], ['PUT', '/api/v1/sites/3']]) {
    const response = await fetch(origin + route, { method, headers, body: '{}' }); assert.equal(response.status, 405);
  }
  assert.equal((await fetch(origin + '/api/v1/sites/3')).status, 404);
  assert.equal((await fetch(origin + '/api/v1/not-simulated')).status, 404);
  assert.deepEqual(await (await fetch(origin + '/__simulation/journal')).json(), []);
});
test('rejects company transfer, dates and other unexpected PATCH fields', async () => {
  const headers = await session();
  for (const body of [{ company_id: 2 }, { created_at: 'raw' }, { updated_at: 'raw' }, { extra: true }]) {
    const response = await fetch(origin + '/api/v1/sites/9001', { method: 'PATCH', headers, body: JSON.stringify(body) });
    assert.equal(response.status, 422);
  }
  assert.deepEqual(await (await fetch(origin + '/__simulation/journal')).json(), []);
});
test('fails closed on malformed, non-JSON or oversized bodies and missing assets', async () => {
  const headers = await session();
  assert.equal((await fetch(origin + '/api/v1/sites', { method: 'POST', headers, body: '{' })).status, 400);
  assert.equal((await fetch(origin + '/api/v1/sites', { method: 'POST', headers: { ...headers, 'Content-Type': 'text/plain' }, body: '{}' })).status, 415);
  assert.equal((await fetch(origin + '/api/v1/sites', { method: 'POST', headers, body: JSON.stringify({ ...createBody, description: 'x'.repeat(17000) }) })).status, 413);
  assert.equal((await fetch(origin + '/missing.js')).status, 404);
  assert.equal((await fetch(origin + '/main.js')).status, 200);
});
test('does not use any fallback if the distribution is unavailable and resets memory between runs', async () => {
  await assert.rejects(createSitesSimulation(path.join(root, 'absent')));
  await writeFile(path.join(root, 'assets', 'index.html'), '<html>No body for the isolation banner</html>');
  await assert.rejects(createSitesSimulation(path.join(root, 'assets')), /startup blocked/);
  const status = await (await fetch(origin + '/__simulation/status')).json();
  const other = await createSitesSimulation(root);
  try {
    await new Promise(resolve => other.listen(0, '127.0.0.1', resolve));
    const otherOrigin = `http://127.0.0.1:${other.address().port}`;
    const next = await (await fetch(otherOrigin + '/__simulation/status')).json();
    assert.notEqual(next.run, status.run);
    const headers = await session();
    assert.equal((await fetch(otherOrigin + '/api/v1/sites', { method: 'POST', headers: { ...headers, Origin: otherOrigin }, body: JSON.stringify(createBody) })).status, 503);
    assert.equal((await (await fetch(otherOrigin + '/api/v1/sites')).json()).total, 1);
  } finally { other.closeAllConnections(); await new Promise(resolve => other.close(resolve)); }
});
