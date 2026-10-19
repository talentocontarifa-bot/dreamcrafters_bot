/**
 * get_youtube_token.js — Autorizador de YouTube Shorts para Dreamcrafters
 */
const http = require('http');
const url = require('url');
const fs = require('fs');
const path = require('path');
let axios;
try {
  axios = require('axios');
} catch (e) {
  axios = require(path.join(__dirname, '..', 'rattle', 'node_modules', 'axios'));
}
require(path.join(__dirname, '..', 'rattle', 'node_modules', 'dotenv')).config({ path: path.join(__dirname, '.env') });

const SCOPES = [
  'https://www.googleapis.com/auth/youtube.upload',
  'https://www.googleapis.com/auth/youtube'
].join(' ');

const REDIRECT_PORT = 3000;
const REDIRECT_URI = `http://localhost:${REDIRECT_PORT}/oauth2callback`;

function saveEnvVars(vars) {
  const envPath = path.join(__dirname, '.env');
  let envContent = fs.existsSync(envPath) ? fs.readFileSync(envPath, 'utf-8') : '';
  for (const [key, val] of Object.entries(vars)) {
    if (!val) continue;
    const regex = new RegExp(`^${key}=.*$`, 'm');
    if (regex.test(envContent)) {
      envContent = envContent.replace(regex, `${key}=${val}`);
    } else {
      envContent += `\n${key}=${val}`;
    }
  }
  fs.writeFileSync(envPath, envContent.trim() + '\n', 'utf-8');
}

async function main() {
  const clientId = process.env.YOUTUBE_CLIENT_ID;
  const clientSecret = process.env.YOUTUBE_CLIENT_SECRET;

  const authUrl = `https://accounts.google.com/o/oauth2/v2/auth?` +
    `client_id=${encodeURIComponent(clientId)}&` +
    `redirect_uri=${encodeURIComponent(REDIRECT_URI)}&` +
    `response_type=code&` +
    `scope=${encodeURIComponent(SCOPES)}&` +
    `access_type=offline&` +
    `prompt=consent`;

  console.log('\n🔗 Enlace de autorización de YouTube para Dreamcrafters:');
  console.log(authUrl);
  console.log(`\n⏳ Esperando autorización en ${REDIRECT_URI}...`);

  const server = http.createServer(async (req, res) => {
    try {
      const parsedUrl = url.parse(req.url, true);
      if (parsedUrl.pathname === '/oauth2callback') {
        const code = parsedUrl.query.code;
        const error = parsedUrl.query.error;
        if (error) {
          res.writeHead(400, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end(`<h1>Error: ${error}</h1>`);
          server.close();
          process.exit(1);
        }
        if (code) {
          const params = new URLSearchParams({
            code,
            client_id: clientId,
            client_secret: clientSecret,
            redirect_uri: REDIRECT_URI,
            grant_type: 'authorization_code'
          });
          const tokenRes = await axios.post('https://oauth2.googleapis.com/token', params.toString(), {
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
          });
          const { access_token, refresh_token } = tokenRes.data;

          // Verificar canal conectado
          const chRes = await axios.get('https://www.googleapis.com/youtube/v3/channels', {
            params: { part: 'snippet', mine: true },
            headers: { Authorization: `Bearer ${access_token}` }
          });
          const ch = chRes.data?.items?.[0];
          const chTitle = ch ? ch.snippet.title : 'Sin canal detectado';

          saveEnvVars({
            YOUTUBE_REFRESH_TOKEN: refresh_token,
            YOUTUBE_PRIVACY_STATUS: 'public'
          });

          console.log(`\n🎉 ¡YouTube conectado con éxito! Canal: "${chTitle}"`);
          res.writeHead(200, { 'Content-Type': 'text/html; charset=utf-8' });
          res.end(`<h1>✅ ¡Canal de YouTube "${chTitle}" conectado a Dreamcrafters!</h1><p>Ya puedes cerrar esta pestaña.</p>`);
          server.close();
          process.exit(0);
        }
      }
    } catch (e) {
      console.error('❌ Error:', e.response?.data || e.message);
      res.writeHead(500, { 'Content-Type': 'text/html; charset=utf-8' });
      res.end(`<h1>Error: ${e.message}</h1>`);
      server.close();
      process.exit(1);
    }
  });

  server.listen(REDIRECT_PORT);
}

main();
