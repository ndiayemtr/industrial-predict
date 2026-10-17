// Local test tooling only. No proxy, upstream client, database or persistence.
import { createServer } from 'node:http';
import { randomUUID } from 'node:crypto';
import { readFile, realpath } from 'node:fs/promises';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

export const simulationHeader = 'sites-isolated-v1';
export const simulationCsp = "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; form-action 'self'; base-uri 'self'; object-src 'none'; frame-ancestors 'none'";
const dates = { created_at: '2026-10-01T10:00:00', updated_at: '2026-10-01T10:00:00' };

export async function createSitesSimulation(dist) {
  const root = await realpath(dist);
  const index = await readFile(path.join(root, 'index.html'), 'utf8');
  if (!index.includes('<body>')) throw new Error('Simulation banner cannot be installed; startup blocked');
  // Angular's optimized CSS loader uses an inline onload handler. Load its
  // stylesheet directly in this response, retaining the strict script CSP.
  const shell = index.replace(/<link\b[^>]*rel="stylesheet"[^>]*>/g,
    tag => tag.replace(/\s+media="print"/g, '').replace(/\s+onload="[^"]*"/g, ''));
  const run = randomUUID();
  const cookie = `ipa_sites_simulation=${run}`;
  const company = { id: 9001, name: 'Entreprise de simulation', code: 'SIM-COMPANY', description: null, ...dates };
  const sites = [{ id: 9001, company_id: company.id, name: 'Site de simulation', code: 'SIM-SITE-001', description: null, ...dates }];
  let nextId = 9002;
  const journal = [];
  const insideRoot = file => file.startsWith(root + path.sep);
  const mime = { '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.woff2': 'font/woff2', '.ico': 'image/x-icon', '.png': 'image/png' };
  const json = (response, status, body) => { response.writeHead(status, { 'Content-Type': 'application/json' }); response.end(JSON.stringify(body)); };
  const server = createServer(async (request, response) => {
    response.setHeader('X-Industrial-Predict-Simulation', simulationHeader);
    response.setHeader('Content-Security-Policy', simulationCsp);
    response.setHeader('Cache-Control', 'no-store');
    response.setHeader('X-Content-Type-Options', 'nosniff');
    const origin = `http://127.0.0.1:${server.address().port}`;
    try {
      if (request.headers.host !== new URL(origin).host) return json(response, 421, { detail: 'Simulation host mismatch' });
      const url = new URL(request.url, origin);
      const method = request.method;
      if (!['GET', 'POST', 'PATCH'].includes(method)) return json(response, 405, { detail: 'Method blocked; no upstream exists' });
      if (method !== 'GET') {
        if (request.headers.origin !== origin || !request.headers.cookie?.split(';').some(value => value.trim() === cookie)) {
          return json(response, 503, { detail: 'Simulation session not verified; submission blocked' });
        }
        if (request.headers['content-type']?.split(';')[0] !== 'application/json') return json(response, 415, { detail: 'JSON required' });
        const match = /^\/api\/v1\/sites\/(\d+)$/.exec(url.pathname);
        if (!(method === 'POST' && url.pathname === '/api/v1/sites') && !(method === 'PATCH' && match)) {
          return json(response, 405, { detail: 'Write route blocked; no upstream exists' });
        }
        let raw = '';
        for await (const chunk of request) {
          raw += chunk;
          if (Buffer.byteLength(raw) > 16384) return json(response, 413, { detail: 'Simulation body limit exceeded' });
        }
        let body;
        try { body = JSON.parse(raw); } catch { return json(response, 400, { detail: 'Invalid JSON' }); }
        const allowed = method === 'POST' ? ['name', 'code', 'description', 'company_id'] : ['name', 'code', 'description'];
        if (!body || Array.isArray(body) || typeof body !== 'object' || Object.keys(body).some(key => !allowed.includes(key))) {
          return json(response, 422, { detail: 'Fields outside the simulated contract' });
        }
        if ((method === 'POST' && (typeof body.name !== 'string' || typeof body.code !== 'string'))
          || ['name', 'code'].some(key => Object.hasOwn(body, key) && typeof body[key] !== 'string')
          || (Object.hasOwn(body, 'description') && body.description !== null && typeof body.description !== 'string')) {
          return json(response, 422, { detail: 'Invalid simulated field types' });
        }
        const site = method === 'PATCH' ? sites.find(item => item.id === Number(match[1])) : null;
        journal.push({ method, path: url.pathname, body: structuredClone(body) });
        if (method === 'PATCH' && !site) return json(response, 404, { detail: 'Simulated site not found' });
        if (method === 'POST' && body.company_id !== company.id) return json(response, 409, { detail: 'Simulated conflict' });
        if (Object.hasOwn(body, 'code') && sites.some(item => item.code === body.code && item.id !== site?.id)) {
          return json(response, 409, { detail: 'Simulated conflict' });
        }
        if (method === 'POST') {
          const created = { id: nextId++, company_id: company.id, name: body.name, code: body.code, description: body.description ?? null, ...dates };
          sites.push(created); return json(response, 201, created);
        }
        Object.assign(site, body, { updated_at: new Date().toISOString() });
        return json(response, 200, site);
      }
      if (url.pathname === '/__simulation/status') return json(response, 200, { mode: simulationHeader, run, upstream: null, persistence: 'memory-only' });
      if (url.pathname === '/__simulation/journal') return json(response, 200, journal);
      if (url.pathname === '/api/v1/companies/9001') return json(response, 200, company);
      if (url.pathname === '/api/v1/companies' || url.pathname === '/api/v1/sites') {
        const page = Number(url.searchParams.get('page') ?? 1), size = Number(url.searchParams.get('page_size') ?? 20);
        if (!Number.isSafeInteger(page) || page < 1 || !Number.isSafeInteger(size) || size < 1 || size > 100) return json(response, 422, { detail: 'Invalid pagination' });
        let items = url.pathname.endsWith('companies') ? [company] : sites.filter(item => !url.searchParams.has('company_id') || item.company_id === Number(url.searchParams.get('company_id')));
        const search = url.searchParams.get('search')?.toLowerCase();
        if (search) items = items.filter(item => `${item.name} ${item.code}`.toLowerCase().includes(search));
        return json(response, 200, { items: items.slice((page - 1) * size, page * size), total: items.length, page, page_size: size, pages: Math.ceil(items.length / size) });
      }
      const match = /^\/api\/v1\/sites\/(\d+)$/.exec(url.pathname);
      if (match) { const site = sites.find(item => item.id === Number(match[1])); return json(response, site ? 200 : 404, site ?? { detail: 'Simulated site not found' }); }
      if (url.pathname.startsWith('/api/') || url.pathname.startsWith('/__simulation/')) return json(response, 404, { detail: 'Not simulated; no upstream exists' });
      const file = path.resolve(root, '.' + decodeURIComponent(url.pathname));
      if (!insideRoot(file) && file !== root) return json(response, 403, { detail: 'Outside static root' });
      if (!path.extname(file) || file === root) {
        response.setHeader('Set-Cookie', `${cookie}; HttpOnly; SameSite=Strict; Path=/`);
        response.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
        response.end(shell.replace('<body>', '<body><aside role="note" style="padding:8px;background:#fff4cc;color:#172b4d;font-weight:bold">SIMULATION ISOLEE - donnees fictives en memoire, aucun acces FastAPI/PostgreSQL.</aside>'));
        return;
      }
      const resolved = await realpath(file);
      if (!insideRoot(resolved)) return json(response, 403, { detail: 'Outside static root' });
      const content = await readFile(resolved);
      response.writeHead(200, { 'Content-Type': mime[path.extname(resolved)] ?? 'application/octet-stream' }); response.end(content);
    } catch {
      if (!response.headersSent) json(response, 404, { detail: 'Simulation resource unavailable; no upstream exists' });
      else response.end();
    }
  });
  return server;
}

if (process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  // The fixed loopback port is separate from Angular and FastAPI. No fallback.
  if (process.argv.length !== 3) throw new Error('Usage: node scripts/sites-simulation-server.mjs <production-browser-directory>');
  const server = await createSitesSimulation(path.resolve(process.argv[2]));
  server.on('error', error => { console.error(`Simulation stopped: ${error.code}`); process.exitCode = 1; });
  server.listen(8098, '127.0.0.1', () => console.log('SIMULATION ISOLEE: http://127.0.0.1:8098/sites?company_id=9001 - no upstream, memory only'));
}
