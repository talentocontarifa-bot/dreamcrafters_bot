/**
 * setup_meta.js — Configurador automático de Facebook Page + Instagram Business para Dreamcrafter
 *
 * Uso:
 *   node setup_meta.js <USER_OR_PAGE_TOKEN> [META_APP_SECRET]
 */
const fs = require('fs');
const path = require('path');
let axios;
try {
  axios = require('axios');
} catch (e) {
  axios = require(path.join(__dirname, '..', 'rattle', 'node_modules', 'axios'));
}

const ENV_PATH = path.join(__dirname, '.env');
const GRAPH_VERSION = 'v21.0';
const DEFAULT_APP_ID = '1358020046140987'; // App: talento_con_tarifa

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
  const inputToken = process.argv[2] || process.env.SHORT_LIVED_TOKEN || process.env.META_PAGE_ACCESS_TOKEN;
  const appSecret = process.argv[3] || process.env.META_APP_SECRET;
  const appId = process.env.META_APP_ID || DEFAULT_APP_ID;

  if (!inputToken) {
    console.log('❌ Pasa el token como argumento: node setup_meta.js <TU_TOKEN>');
    process.exit(1);
  }

  let tokenToUse = inputToken.trim();

  // 1. Si nos dieron el App Secret, canjear por User Token de larga duración (60 días -> Page Token perpetuo)
  if (appSecret) {
    try {
      console.log('🔄 Canjeando por User Token de larga duración (para obtener Page Token perpetuo)...');
      const exRes = await axios.get(`https://graph.facebook.com/${GRAPH_VERSION}/oauth/access_token`, {
        params: {
          grant_type: 'fb_exchange_token',
          client_id: appId,
          client_secret: appSecret.trim(),
          fb_exchange_token: tokenToUse
        }
      });
      if (exRes.data?.access_token) {
        tokenToUse = exRes.data.access_token;
        console.log('✅ User Long-Lived Token generado con éxito.');
      }
    } catch (e) {
      console.warn('⚠️ No se pudo canjear con App Secret (quizá ya es un Page Token):', e.response?.data?.error?.message || e.message);
    }
  }

  // 2. Inspeccionar qué tipo de token es y listar todas las páginas disponibles
  console.log('\n🔍 Consultando páginas de Facebook e Instagram vinculadas...');
  try {
    const accountsRes = await axios.get(`https://graph.facebook.com/${GRAPH_VERSION}/me/accounts`, {
      params: {
        fields: 'id,name,access_token,instagram_business_account{id,username,name}',
        access_token: tokenToUse
      }
    });

    const pages = accountsRes.data?.data || [];
    if (pages.length === 0) {
      console.log('⚠️ El token es válido pero no devolvió páginas en /me/accounts.');
      console.log('💡 Asegúrate de haber marcado la página de Dreamcrafter al generar el token en Graph API Explorer.');
      return;
    }

    console.log(`\n📄 Se encontraron ${pages.length} página(s):\n`);
    for (const p of pages) {
      const ig = p.instagram_business_account;
      console.log(`  📘 Página FB: "${p.name}" (ID: ${p.id})`);
      if (ig) {
        console.log(`  📸 Instagram vinculado: @${ig.username} (${ig.name || ''}) -> ID: ${ig.id}`);
      } else {
        console.log(`  ⚠️ Sin cuenta de Instagram Business/Creator vinculada.`);
      }
      console.log('  --------------------------------------------------');
    }

    // Buscar automáticamente si alguna se llama Dreamcrafter (o elegir la que no sea Talento con Tarifa si solo hay otra)
    let target = pages.find(p => /dream\s*crafter/i.test(p.name) || /dream\s*crafter/i.test(p.instagram_business_account?.username || ''));
    if (!target && pages.length === 1) {
      target = pages[0];
    }

    if (target) {
      console.log(`\n🎯 Seleccionada automáticamente: "${target.name}"`);
      saveEnvVars({
        META_PAGE_ID: target.id,
        META_PAGE_ACCESS_TOKEN: target.access_token,
        INSTAGRAM_ACCOUNT_ID: target.instagram_business_account?.id || ''
      });
      console.log(`💾 Guardado en ${ENV_PATH}:`);
      console.log(`   META_PAGE_ID=${target.id}`);
      console.log(`   INSTAGRAM_ACCOUNT_ID=${target.instagram_business_account?.id || '(PENDIENTE VINCULAR IG)'}`);
      console.log(`   META_PAGE_ACCESS_TOKEN=${target.access_token.slice(0, 18)}...`);
    } else {
      console.log('\nℹ️ Dime cuál de las páginas listadas arriba es la de Dreamcrafter para guardarla.');
    }
  } catch (err) {
    // Quizás pegó directamente un Page Access Token en vez de un User Token
    console.log('ℹ️ El token parece ser directo de Página. Consultando /me directamente...');
    try {
      const pageRes = await axios.get(`https://graph.facebook.com/${GRAPH_VERSION}/me`, {
        params: {
          fields: 'id,name,instagram_business_account{id,username,name}',
          access_token: tokenToUse
        }
      });
      const p = pageRes.data;
      const ig = p.instagram_business_account;
      console.log(`\n📘 Página FB detectada: "${p.name}" (ID: ${p.id})`);
      if (ig) {
        console.log(`📸 Instagram vinculado: @${ig.username} -> ID: ${ig.id}`);
      } else {
        console.log(`⚠️ Esta página no muestra un Instagram Business/Creator vinculado.`);
      }
      saveEnvVars({
        META_PAGE_ID: p.id,
        META_PAGE_ACCESS_TOKEN: tokenToUse,
        INSTAGRAM_ACCOUNT_ID: ig?.id || ''
      });
      console.log(`💾 Guardado en ${ENV_PATH}`);
    } catch (err2) {
      console.error('❌ Error consultando Graph API:', err2.response?.data?.error?.message || err2.message);
    }
  }
}

main();
