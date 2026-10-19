/**
 * publish_video.js — Orquestador de publicación de Reels de DreamCrafters (Facebook + Instagram)
 */
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const { publishVideoToFacebook } = require('./facebook_publisher');
const { publishReelToInstagram } = require('./instagram_publisher');

const VIDEO_PATH = process.env.VIDEO_PATH || path.join(__dirname, 'out', 'video_final_dreamcrafters.mp4');

const DEFAULT_TITLE = '🎮 ¡Invitaciones que se juegan en tu celular! ✨ Super Mario Galaxy & Minecraft | DreamCrafters';
const DEFAULT_CAPTION = [
  '🍄 ¿Otra imagen fija en WhatsApp? ¡Conviértela en un videojuego real desde el celular! 🎮✨',
  '',
  'En DreamCrafters tus invitados atrapan monedas espaciales para desbloquear:',
  '✅ Cuenta regresiva en vivo',
  '✅ Ubicación exacta en Google Maps',
  '✅ Confirmación de asistencia en 1 toque a tu WhatsApp',
  '',
  '🟩 ¡Además puedes crear GRATIS la invitación interactiva de Minecraft en 60 segundos!',
  '👉 Entra hoy a https://dreamcrafters.lat',
  '',
  '#DreamCrafters #InvitacionesDigitales #SuperMarioGalaxy #MinecraftParty #FiestasInfantiles #InvitacionesInteractivas'
].join('\n');

async function main() {
  const args = process.argv.slice(2);
  const checkOnly = args.includes('--check-config');

  const pageId = process.env.META_PAGE_ID;
  const token = process.env.META_PAGE_ACCESS_TOKEN;

  if (!pageId || !token) {
    console.error('❌ Faltan META_PAGE_ID o META_PAGE_ACCESS_TOKEN en las variables de entorno.');
    process.exit(1);
  }

  if (checkOnly) {
    console.log(`✅ Configuración Meta verificada (META_PAGE_ID: ${pageId})`);
    return;
  }

  if (!fs.existsSync(VIDEO_PATH)) {
    throw new Error(`No se encontró el video renderizado en: ${VIDEO_PATH}`);
  }

  const results = {
    timestamp: new Date().toISOString(),
    facebook: null,
    instagram: null
  };

  // 1. Publicar en Facebook Reels
  try {
    results.facebook = await publishVideoToFacebook(VIDEO_PATH, {
      title: DEFAULT_TITLE,
      description: DEFAULT_CAPTION
    });
  } catch (fbErr) {
    console.error('⚠️ Error publicando en Facebook:', fbErr.message);
    results.facebook = { success: false, error: fbErr.message };
  }

  // 2. Publicar en Instagram Reels (si la cuenta IG ya está vinculada a la página)
  try {
    results.instagram = await publishReelToInstagram(VIDEO_PATH, {
      caption: DEFAULT_CAPTION,
      share_to_feed: true
    });
  } catch (igErr) {
    console.warn('ℹ️ Aviso Instagram (opcional si aún no está vinculado):', igErr.message);
    results.instagram = { success: false, error: igErr.message };
  }

  fs.mkdirSync(path.join(__dirname, 'out'), { recursive: true });
  fs.writeFileSync(
    path.join(__dirname, 'out', 'publication-state.json'),
    JSON.stringify(results, null, 2),
    'utf-8'
  );

  if (!results.facebook?.success && !results.instagram?.success) {
    process.exit(1);
  }
}

main().catch(err => {
  console.error('❌ Error fatal en publish_video.js:', err.message);
  process.exit(1);
});
