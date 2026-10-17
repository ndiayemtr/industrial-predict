// Development-only dev-server proxy. No target on port 8000, no fallback.
const fs = require('node:fs');
const path = require('node:path');
const file = process.env.INDUSTRIAL_PREDICT_DEV_CONFIG;
if (!file) throw new Error('Development explicit configuration required');
const config = JSON.parse(fs.readFileSync(file, 'utf8'));
if (config.mode !== 'local-development' || config.database !== 'industrial_predict_dev' || config.api_port !== 8001 || config.db_port !== 5434 || config.db_host !== '127.0.0.1' || !/^[0-9a-f-]{36}$/.test(config.instance_id ?? '') || path.resolve(file).startsWith(path.resolve(__dirname, '../..') + path.sep)) {
  throw new Error('Development target mismatch; startup blocked');
}
const target = 'http://127.0.0.1:8001';
async function bypass(req, res) {
  try {
    const response = await fetch(target + '/__dev/identity', { signal: AbortSignal.timeout(2000), redirect: 'error' });
    const proof = await response.json();
    if (!response.ok || response.headers.get('x-industrial-predict-environment') !== 'local-development' || proof.mode !== config.mode || proof.database !== config.database || proof.instance_id !== config.instance_id || proof.role !== 'ui47_app' || proof.revision !== '09ac8101e9fe' || proof.superuser !== false) throw new Error('Wrong API identity');
  } catch {
    if (res) {
      res.statusCode = 503;
      res.setHeader('Content-Type', 'application/json');
      res.end(JSON.stringify({ detail: 'Development identity check failed; proxy request blocked' }));
      // Vite stops here when bypass returns a string and the response has ended.
      return req.url;
    }
    return false;
  }
}
module.exports = {
  '/api/v1/**': { target, changeOrigin: true, bypass },
  '/__dev/**': { target, changeOrigin: true, bypass }
};
