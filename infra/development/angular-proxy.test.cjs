const { test, after } = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const directory = fs.mkdtempSync(path.join(os.tmpdir(), 'development-proxy-'));
const file = path.join(directory, 'config.json');
const modulePath = require.resolve('./angular-proxy.cjs');
const initialEnv = process.env.INDUSTRIAL_PREDICT_DEV_CONFIG;
const initialFetch = global.fetch;
const config = { mode:'local-development',database:'industrial_predict_dev',api_port:8001,
  db_port:5434,db_host:'127.0.0.1',instance_id:'00000000-0000-0000-0000-000000000001' };
const proof = { ...config,role:'ui47_app',revision:'09ac8101e9fe',superuser:false };
function load(value = config) {
  fs.writeFileSync(file, JSON.stringify(value));
  process.env.INDUSTRIAL_PREDICT_DEV_CONFIG = file;
  delete require.cache[modulePath];
  return require(modulePath);
}
function response(value = proof, marker = 'local-development') {
  return { ok:true,headers:new Headers({'x-industrial-predict-environment':marker}),json:async () => value };
}
after(() => {
  global.fetch = initialFetch;
  if (initialEnv === undefined) delete process.env.INDUSTRIAL_PREDICT_DEV_CONFIG;
  else process.env.INDUSTRIAL_PREDICT_DEV_CONFIG = initialEnv;
  fs.rmSync(directory, {recursive:true});
});
test('missing config blocks startup', () => {
  delete process.env.INDUSTRIAL_PREDICT_DEV_CONFIG;
  delete require.cache[modulePath];
  assert.throws(() => require(modulePath), /explicit configuration/);
});
test('source database and normal API port block startup', () => {
  assert.throws(() => load({...config,database:'industrial_predict'}), /target mismatch/);
  assert.throws(() => load({...config,api_port:8000}), /target mismatch/);
});
test('verified development target permits forwarding, checked on every request', async () => {
  const options = load()['/api/v1/**'];
  assert.equal(options.target, 'http://127.0.0.1:8001');
  let checks = 0;
  global.fetch = async url => { assert.equal(url, options.target+'/__dev/identity'); checks++; return response(); };
  assert.equal(await options.bypass({url:'/api/v1/sites/'}, {}), undefined);
  assert.equal(await options.bypass({url:'/api/v1/companies/'}, {}), undefined);
  assert.equal(checks, 2);
});
for (const [label, result] of [
  ['wrong database', () => response({...proof,database:'industrial_predict'})],
  ['wrong instance', () => response({...proof,instance_id:'another-instance'})],
  ['admin identity', () => response({...proof,role:'ui47_admin',superuser:true})],
  ['wrong migration', () => response({...proof,revision:'old'})],
  ['missing marker', () => response(proof,'')],
  ['API unavailable', () => { throw new Error('offline'); }],
  ['HTTP failure', () => ({...response(),ok:false})]
]) test(label+' blocks request without forwarding', async () => {
  const options = load()['/api/v1/**'];
  global.fetch = async () => result();
  const res = {setHeader() {},end(body) { this.body=body; this.writableEnded=true; }};
  // This is a unit-test request object; no POST is sent to any server.
  const req = {url:'/api/v1/sites/',method:'POST'};
  assert.equal(await options.bypass(req,res), req.url);
  assert.equal(res.statusCode,503);
  assert.equal(res.writableEnded,true);
  assert.match(res.body,/blocked/);
  assert.equal(await options.bypass(req,undefined),false);
});
