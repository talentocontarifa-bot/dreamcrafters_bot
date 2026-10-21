/**
 * publish_video.js — Orquestador Multi-Cuenta y Multi-Plataforma para DreamCrafters + Empujón en Talento con Tarifa
 * =================================================================================================================
 * Publica automáticamente el Reel renderizado en:
 *   1. Ecosistema DreamCrafters Oficial:
 *      - Facebook Reels ("Dreamcrafters - Invitaciones Virtuales IA")
 *      - Instagram Reels (DreamCrafters)
 *   2. Ecosistema Talento con Tarifa (Empujón Cruzado):
 *      - Facebook Reels (Talento con Tarifa)
 *      - Instagram Reels (@talentocontarifa)
 *      - TikTok (Talento con Tarifa)
 *      - YouTube Shorts (Talento con Tarifa)
 *
 * Incluye siempre todas las ligas correspondientes en los campos de texto / descripción / caption.
 */
const fs = require('fs');
const path = require('path');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const { publishVideoToFacebook } = require('./facebook_publisher');
const { publishReelToInstagram } = require('./instagram_publisher');
const { publishVideoToTikTok } = require('./tiktok_publisher');
const { publishVideoToYouTube } = require('./youtube_publisher');

const VIDEOS_DIR = path.join(__dirname, 'videos');

function resolveVideoPath() {
  if (process.env.VIDEO_PATH && process.env.VIDEO_PATH !== 'auto') {
    const customPath = path.isAbsolute(process.env.VIDEO_PATH)
      ? process.env.VIDEO_PATH
      : path.join(VIDEOS_DIR, path.basename(process.env.VIDEO_PATH));
    if (fs.existsSync(customPath)) return customPath;
    const relPath = path.resolve(__dirname, process.env.VIDEO_PATH);
    if (fs.existsSync(relPath)) return relPath;
  }

  if (fs.existsSync(VIDEOS_DIR)) {
    const mp4Files = fs
      .readdirSync(VIDEOS_DIR)
      .filter(f => f.toLowerCase().endsWith('.mp4'))
      .sort();
    if (mp4Files.length > 0) {
      // Rotación determinística por bloque de 12 horas (turno mañana / tarde) cuando hay varios videos
      const slotIndex = Math.floor(Date.now() / (12 * 3600 * 1000)) % mp4Files.length;
      const chosen = mp4Files[slotIndex];
      console.log(`🎬 Videos disponibles en videos/: [${mp4Files.join(', ')}] -> Seleccionado: ${chosen}`);
      return path.join(VIDEOS_DIR, chosen);
    }
  }

  return path.join(__dirname, 'out', 'video_final_dreamcrafters.mp4');
}

const VIDEO_PATH = resolveVideoPath();
const IS_MINECRAFT_VIDEO = /steve|minecraft/i.test(path.basename(VIDEO_PATH));

// Ligas oficiales que SIEMPRE van en los campos de texto de las redes sociales
const LINKS = {
  mainSite: 'https://dreamcrafters.lat',
  minecraftDemo: 'https://dreamcrafters.lat/invitacionminecraft/ian-level8',
  marioDemo: 'https://dreamcrafters.lat/invitacionmario/index.html',
  agentesDemo: 'https://dreamcrafters.lat/agentes_de_luz',
  tctSite: 'https://talentocontarifa.lat'
};

const DREAMCRAFTERS_TITLE = IS_MINECRAFT_VIDEO
  ? '👑⚔️ ¡Crea GRATIS tu invitación interactiva de Minecraft! | DreamCrafters'
  : '🎮 ¡Invitaciones que se juegan en tu celular! ✨ Super Mario Galaxy & Minecraft | DreamCrafters';

const DREAMCRAFTERS_CAPTION = IS_MINECRAFT_VIDEO
  ? [
      '👑⚔️ ¡El Rey Steve tiene un regalo para tu próxima fiesta! Crea 100% GRATIS tu invitación interactiva de Minecraft.',
      '',
      'Tus invitados abren el link en su celular, derrotan al Enderman a espadazos y desbloquean:',
      '✨ Música épica + Cuenta regresiva',
      '📍 Mapa GPS en Google Maps',
      '📲 Confirmación en 1 toque a tu WhatsApp',
      '',
      `👉 Créala gratis en 60 segundos: ${LINKS.mainSite}`,
      `🗡️ Prueba el demo en vivo: ${LINKS.minecraftDemo}`,
      '',
      '#DreamCrafters #MinecraftParty #InvitacionesDigitales #FiestasInfantiles #InvitacionesMinecraft #CumpleañosMinecraft'
    ].join('\n')
  : [
      '🍄 ¿Otra imagen fija en WhatsApp? ¡Conviértela en un videojuego real desde el celular! 🎮✨',
      '',
      'En DreamCrafters tus invitados abren el enlace en su teléfono y juegan para desbloquear todos los detalles de tu fiesta:',
      '✅ Minijuego interactivo sin instalar apps',
      '✅ Música épica y cuenta regresiva en vivo',
      '✅ Ubicación exacta en Google Maps',
      '✅ Confirmación de asistencia en 1 toque directo a tu WhatsApp',
      '',
      '🟩 ¡CREA GRATIS LA INVITACIÓN DE MINECRAFT EN 60 SEGUNDOS!',
      `👉 Crea la tuya aquí: ${LINKS.mainSite}`,
      `🕹️ Juega el demo de Super Mario Galaxy: ${LINKS.marioDemo}`,
      `⚡ Ver evento interactivo Agentes de Luz: ${LINKS.agentesDemo}`,
      '',
      '#DreamCrafters #InvitacionesDigitales #SuperMarioGalaxy #MinecraftParty #FiestasInfantiles #InvitacionesInteractivas #CumpleañosInfantiles'
    ].join('\n');

const TCT_CROSSPROMO_TITLE = IS_MINECRAFT_VIDEO
  ? '👑⚔️ ¡Regalamos invitaciones interactivas de Minecraft que se juegan en el celular! | DreamCrafters'
  : '🚀 ¡Creamos invitaciones infantiles que son videojuegos reales en el celular! 🎮✨ | DreamCrafters x Talento con Tarifa';

const TCT_CROSSPROMO_CAPTION = IS_MINECRAFT_VIDEO
  ? [
      '👑⚔️ ¿Tienes fiesta en puerta? En DreamCrafters liberamos GRATIS el creador de invitaciones interactivas de Minecraft.',
      '',
      'Tus invitados derrotan al Enderman desde su celular para desbloquear la ubicación GPS, cuenta regresiva y confirmación directa a tu WhatsApp 🎮✨',
      '',
      `👉 Crea la tuya gratis aquí: ${LINKS.mainSite}`,
      `🗡️ Juega el demo: ${LINKS.minecraftDemo}`,
      `⚡ Impulsado por Talento con Tarifa: ${LINKS.tctSite}`,
      '',
      '#DreamCrafters #Minecraft #InvitacionesDigitales #FiestasInfantiles #TalentoConTarifa #Reels #Shorts'
    ].join('\n')
  : [
      '🍄 ¿Ya viste nuestro nuevo proyecto en vivo? En lugar de mandar una imagen estática por WhatsApp, en DreamCrafters convertimos las invitaciones infantiles en un videojuego real desde el celular 🎮✨',
      '',
      'Tus invitados atrapan monedas espaciales para desbloquear cuenta regresiva, mapa GPS en Google Maps y confirmación en 1 toque a WhatsApp.',
      '',
      '🔗 LIGAS OFICIALES PARA PROBARLO HOY:',
      `👉 Sitio Web + Creador GRATIS de Minecraft: ${LINKS.mainSite}`,
      `🕹️ Juega la invitación de Super Mario Galaxy: ${LINKS.marioDemo}`,
      `⚡ Mira el pase interactivo Agentes de Luz: ${LINKS.agentesDemo}`,
      '',
      '─────────────────────────',
      '🤖 Desarrollo interactivo y automatización con IA impulsado por Talento con Tarifa.',
      `⚡ Digitaliza o automatiza tu negocio hoy: ${LINKS.tctSite}`,
      '',
      '#DreamCrafters #TalentoConTarifa #SuperMarioGalaxy #Minecraft #InvitacionesDigitales #FiestasInfantiles #DesarrolloWeb #InteligenciaArtificial #Reels #Shorts'
    ].join('\n');

async function main() {
  const args = process.argv.slice(2);
  const checkOnly = args.includes('--check-config');

  const dcPageId = process.env.META_PAGE_ID;
  const dcToken = process.env.META_PAGE_ACCESS_TOKEN;

  const tctPageId = process.env.TCT_META_PAGE_ID;
  const tctToken = process.env.TCT_META_PAGE_ACCESS_TOKEN;
  const tctIgId = process.env.TCT_INSTAGRAM_ACCOUNT_ID;

  if (!dcPageId || !dcToken) {
    console.error('❌ Faltan META_PAGE_ID o META_PAGE_ACCESS_TOKEN (DreamCrafters) en las variables de entorno.');
    process.exit(1);
  }

  if (checkOnly) {
    console.log(`✅ Credenciales DreamCrafters listas (Page ID: ${dcPageId})`);
    if (tctPageId && tctToken) {
      console.log(`✅ Credenciales Empujón Talento con Tarifa listas (Page ID: ${tctPageId}, IG ID: ${tctIgId || 'auto'})`);
    }
    if (process.env.TIKTOK_REFRESH_TOKEN) console.log('✅ Credenciales TikTok (Talento con Tarifa) listas');
    if (process.env.YOUTUBE_REFRESH_TOKEN) console.log('✅ Credenciales YouTube Shorts (Talento con Tarifa) listas');
    return;
  }

  if (!fs.existsSync(VIDEO_PATH)) {
    throw new Error(`No se encontró el video renderizado en: ${VIDEO_PATH}`);
  }

  const results = {
    timestamp: new Date().toISOString(),
    links_included: LINKS,
    dreamcrafters: {
      facebook: null,
      instagram: null
    },
    talento_con_tarifa: {
      facebook: null,
      instagram: null,
      tiktok: null,
      youtube: null
    }
  };

  // =========================================================================
  // 1. PUBLICACIÓN EN REDES OFICIALES DE DREAMCRAFTERS
  // =========================================================================
  console.log('\n====================================================');
  console.log('🌟 1/2 PUBLICANDO EN REDES OFICIALES: DREAMCRAFTERS');
  console.log('====================================================');

  try {
    results.dreamcrafters.facebook = await publishVideoToFacebook(VIDEO_PATH, {
      title: DREAMCRAFTERS_TITLE,
      description: DREAMCRAFTERS_CAPTION,
      pageId: dcPageId,
      accessToken: dcToken,
      label: 'DreamCrafters FB'
    });
  } catch (err) {
    console.error('⚠️ Error en Facebook (DreamCrafters):', err.message);
    results.dreamcrafters.facebook = { success: false, error: err.message };
  }

  try {
    results.dreamcrafters.instagram = await publishReelToInstagram(VIDEO_PATH, {
      caption: DREAMCRAFTERS_CAPTION,
      share_to_feed: true,
      pageId: dcPageId,
      igAccountId: process.env.INSTAGRAM_ACCOUNT_ID || null,
      accessToken: dcToken
    });
  } catch (err) {
    console.warn('ℹ️ Aviso Instagram (DreamCrafters):', err.message);
    results.dreamcrafters.instagram = { success: false, error: err.message };
  }

  // =========================================================================
  // 2. EMPUJÓN CRUZADO EN TODAS LAS REDES DE TALENTO CON TARIFA
  // =========================================================================
  console.log('\n====================================================');
  console.log('🚀 2/2 EMPUJÓN CRUZADO EN REDES: TALENTO CON TARIFA');
  console.log('====================================================');

  if (tctPageId && tctToken) {
    try {
      results.talento_con_tarifa.facebook = await publishVideoToFacebook(VIDEO_PATH, {
        title: TCT_CROSSPROMO_TITLE,
        description: TCT_CROSSPROMO_CAPTION,
        pageId: tctPageId,
        accessToken: tctToken,
        label: 'TalentoConTarifa FB'
      });
    } catch (err) {
      console.error('⚠️ Error en Facebook (Talento con Tarifa):', err.message);
      results.talento_con_tarifa.facebook = { success: false, error: err.message };
    }

    try {
      results.talento_con_tarifa.instagram = await publishReelToInstagram(VIDEO_PATH, {
        caption: TCT_CROSSPROMO_CAPTION,
        share_to_feed: true,
        pageId: tctPageId,
        igAccountId: tctIgId || null,
        accessToken: tctToken
      });
    } catch (err) {
      console.error('⚠️ Error en Instagram (Talento con Tarifa):', err.message);
      results.talento_con_tarifa.instagram = { success: false, error: err.message };
    }
  } else {
    console.warn('ℹ️ Credenciales TCT_META_PAGE_ID / TCT_META_PAGE_ACCESS_TOKEN no configuradas.');
  }

  if (process.env.TIKTOK_REFRESH_TOKEN && process.env.TIKTOK_CLIENT_KEY) {
    try {
      results.talento_con_tarifa.tiktok = await publishVideoToTikTok(VIDEO_PATH, {
        title: `${DREAMCRAFTERS_TITLE} 👉 ${LINKS.mainSite} | Demo Mario: ${LINKS.marioDemo} #DreamCrafters #SuperMarioGalaxy #Minecraft #TalentoConTarifa`
      });
    } catch (err) {
      console.error('⚠️ Error en TikTok (Talento con Tarifa):', err.message);
      results.talento_con_tarifa.tiktok = { success: false, error: err.message };
    }
  }

  if (process.env.YOUTUBE_REFRESH_TOKEN && process.env.YOUTUBE_CLIENT_ID) {
    try {
      results.talento_con_tarifa.youtube = await publishVideoToYouTube(VIDEO_PATH, {
        title: '🎮 ¡Invitaciones que se juegan en el celular! Super Mario Galaxy & Minecraft | DreamCrafters #Shorts',
        description: TCT_CROSSPROMO_CAPTION,
        tags: [
          'DreamCrafters',
          'Invitaciones Digitales',
          'Super Mario Galaxy',
          'Minecraft',
          'Fiestas Infantiles',
          'Talento con Tarifa',
          'Shorts'
        ],
        privacyStatus: process.env.YOUTUBE_PRIVACY_STATUS || 'public'
      });
    } catch (err) {
      console.error('⚠️ Error en YouTube Shorts (Talento con Tarifa):', err.message);
      results.talento_con_tarifa.youtube = { success: false, error: err.message };
    }
  }

  fs.mkdirSync(path.join(__dirname, 'out'), { recursive: true });
  fs.writeFileSync(
    path.join(__dirname, 'out', 'publication-state.json'),
    JSON.stringify(results, null, 2),
    'utf-8'
  );

  const anySuccess =
    results.dreamcrafters.facebook?.success ||
    results.dreamcrafters.instagram?.success ||
    results.talento_con_tarifa.facebook?.success ||
    results.talento_con_tarifa.instagram?.success ||
    results.talento_con_tarifa.tiktok?.success ||
    results.talento_con_tarifa.youtube?.success;

  if (!anySuccess) {
    process.exit(1);
  }
}

main().catch(err => {
  console.error('❌ Error fatal en publish_video.js:', err.message);
  process.exit(1);
});
