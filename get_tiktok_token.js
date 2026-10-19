/**
 * get_tiktok_token.js — Autorizador de TikTok API v2 para Dreamcrafters
 *
 * Uso:
 *   1. Para ver el link de autorización:
 *      node dreamcrafter/get_tiktok_token.js
 *   2. Para canjear el código o la URL de regreso:
 *      node dreamcrafter/get_tiktok_token.js "<URL_COMPLETA_O_CODE>"
 */
const fs = require('fs');
const path = require('path');
let axios;
try {
  axios = require('axios');
} catch (e) {
  axios = require(path.join(__dirname, '..', 'rattle', 'node_modules', 'axios'));
}
require(path.join(__dirname, '..', 'rattle', 'node_modules', 'dotenv')).config({ path: path.join(__dirname, '.env') });

const ENV_PATH = path.join(__dirname, '.env');
const TOKEN_FILE = path.join(__dirname, 'tiktok_tokens.json');

function saveEnvVars(vars) {
  let content = fs.existsSync(ENV_PATH) ? fs.readFileSync(ENV_PATH, 'utf-8') : '';
  for (const [key, val] of Object.entries(vars)) {
    if (!val) continue;
    const regex = new RegExp(`^${key}=.*$`, 'm');
    if (regex.test(content)) {
      content = content.replace(regex, `${key}=${val}`);
    } else {
      content += `\n${key}=${val}`;
    }
  }
  fs.writeFileSync(ENV_PATH, content.trim() + '\n', 'utf-8');
}

async function main() {
  const clientKey = process.env.TIKTOK_CLIENT_KEY;
  const clientSecret = process.env.TIKTOK_CLIENT_SECRET;
  const redirectUri = process.env.TIKTOK_REDIRECT_URI;

  const input = process.argv[2];
  if (!input) {
    const authUrl = `https://www.tiktok.com/v2/auth/authorize/?` + new URLSearchParams({
      client_key: clientKey,
      scope: 'user.info.basic,video.publish,video.upload',
      response_type: 'code',
      redirect_uri: redirectUri,
      state: 'dreamcrafter'
    }).toString();

    console.log('\n🎵 Enlace de autorización de TikTok para Dreamcrafters:');
    console.log(authUrl);
    return;
  }

  let code = input.trim();
  if (code.includes('code=')) {
    const m = code.match(/[?&]code=([^&]+)/);
    if (m) code = decodeURIComponent(m[1]);
  }

  console.log('🔄 Intercambiando código por tokens de TikTok...');
  const params = new URLSearchParams({
    client_key: clientKey,
    client_secret: clientSecret,
    code,
    grant_type: 'authorization_code',
    redirect_uri: redirectUri
  });

  const res = await axios.post('https://open.tiktokapis.com/v2/oauth/token/', params.toString(), {
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' }
  });

  const data = res.data;
  if (!data.access_token) {
    console.error('❌ Error al obtener token:', data);
    process.exit(1);
  }

  fs.writeFileSync(TOKEN_FILE, JSON.stringify(data, null, 2), 'utf-8');
  saveEnvVars({
    TIKTOK_ACCESS_TOKEN: data.access_token,
    TIKTOK_REFRESH_TOKEN: data.refresh_token,
    TIKTOK_OPEN_ID: data.open_id
  });

  // Consultar usuario conectado
  try {
    const infoRes = await axios.post('https://open.tiktokapis.com/v2/post/publish/creator_info/query/', {}, {
      headers: {
        Authorization: `Bearer ${data.access_token}`,
        'Content-Type': 'application/json; charset=UTF-8'
      }
    });
    const username = infoRes.data?.data?.creator_username || data.open_id;
    console.log(`\n🎉 ¡TikTok conectado con éxito! Cuenta: @${username}`);
  } catch (e) {
    console.log(`\n🎉 ¡TikTok conectado con éxito! OpenID: ${data.open_id}`);
  }
}

main().catch(err => {
  console.error('❌ Error:', err.response?.data || err.message);
  process.exit(1);
});
