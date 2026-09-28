import { createReadStream, existsSync, statSync } from 'node:fs';
import { createServer, request as proxyRequest } from 'node:http';
import { extname, resolve, sep } from 'node:path';

const port = Number(process.env.PORT || 5173);
const apiTarget = process.env.API_TARGET || 'backend:8000';
const [apiHost, apiPort = '8000'] = apiTarget.split(':');
const root = resolve('/app/dist');
const contentTypes = {
  '.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8',
  '.css': 'text/css; charset=utf-8', '.svg': 'image/svg+xml', '.ico': 'image/x-icon',
  '.json': 'application/json; charset=utf-8', '.png': 'image/png', '.woff2': 'font/woff2',
};

createServer((req, res) => {
  if (req.url === '/healthz') {
    res.writeHead(200, { 'content-type': 'text/plain; charset=utf-8' });
    res.end('ok');
    return;
  }
  if (req.url?.startsWith('/api/')) {
    const upstream = proxyRequest({ hostname: apiHost, port: apiPort,
      path: req.url.slice(4) || '/', method: req.method,
      headers: { ...req.headers, host: apiTarget } }, (response) => {
      res.writeHead(response.statusCode || 502, response.headers);
      response.pipe(res);
    });
    upstream.on('error', () => {
      if (!res.headersSent) res.writeHead(502, { 'content-type': 'application/json' });
      res.end(JSON.stringify({ detail: 'Backend unavailable' }));
    });
    req.pipe(upstream);
    return;
  }
  let pathname;
  try { pathname = decodeURIComponent(new URL(req.url || '/', 'http://localhost').pathname); }
  catch { res.writeHead(400).end('Bad request'); return; }
  const requested = resolve(root, `.${pathname}`);
  const safePath = requested.startsWith(root + sep);
  const isFile = (candidate) => existsSync(candidate) && statSync(candidate).isFile();
  const file = safePath && isFile(requested) ? requested : resolve(root, 'index.html');
  if (!isFile(file)) { res.writeHead(404).end('Not found'); return; }
  res.writeHead(200, { 'content-type': contentTypes[extname(file)] || 'application/octet-stream' });
  if (req.method === 'HEAD') { res.end(); return; }
  createReadStream(file).pipe(res);
}).listen(port, '0.0.0.0');
