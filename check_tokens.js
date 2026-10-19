/**
 * check_tokens.js — Verificador de accesos de Dreamcrafters (Facebook + Instagram)
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

function saveInstagramId(igId) {
  let content = fs.existsSync(ENV_PATH) ? fs.readFileSync(ENV_PATH, 'utf-8') : '';
  const regex = /^INSTAGRAM_ACCOUNT_ID=.*$/m;
  if (regex.test(content)) {
    content = content.replace(regex, `INSTAGRAM_ACCOUNT_ID=${igId}`);
  } else {
    content += `\nINSTAGRAM_ACCOUNT_ID=${igId}`;
  }
  fs.writeFileSync(ENV_PATH, content.trim() + '\n', 'utf-8');
}

async function main() {
  const pageId = process.env.META_PAGE_ID;
  const token = process.env.META_PAGE_ACCESS_TOKEN;

  if (!pageId || !token) {
    console.error('❌ Faltan META_PAGE_ID o META_PAGE_ACCESS_TOKEN en dreamcrafter/.env');
    process.exit(1);
  }

  // 1. Verificar Página de Facebook y cuenta de Instagram vinculada
  const pageRes = await axios.get(`https://graph.facebook.com/v21.0/${pageId}`, {
    params: {
      fields: 'id,name,instagram_business_account{id,username,name}',
      access_token: token
    }
  });

  const dbgRes = await axios.get('https://graph.facebook.com/v21.0/debug_token', {
    params: { input_token: token, access_token: token }
  });

  const dbg = dbgRes.data?.data || {};
  const expiryText = dbg.expires_at === 0 ? 'Perpetuo (Nunca caduca)' : `Expira en timestamp ${dbg.expires_at}`;

  console.log(`📘 Facebook Page: ✅ "${pageRes.data.name}" (ID: ${pageRes.data.id}) · Token: ${expiryText}`);

  const ig = pageRes.data?.instagram_business_account;
  if (ig?.id) {
    console.log(`📸 Instagram:     ✅ @${ig.username} (ID: ${ig.id})`);
    if (process.env.INSTAGRAM_ACCOUNT_ID !== ig.id) {
      saveInstagramId(ig.id);
      console.log('   💾 INSTAGRAM_ACCOUNT_ID guardado automáticamente en dreamcrafter/.env');
    }
  } else {
    console.log('📸 Instagram:     ⏳ Pendiente de vincular a la página (permisos instagram_basic e instagram_content_publish YA incluidos en el token)');
  }
}

main().catch(err => {
  console.error('❌ Error verificando credenciales:', err.response?.data || err.message);
  process.exit(1);
});
