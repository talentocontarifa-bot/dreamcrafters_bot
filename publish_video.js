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
const { execFileSync } = require('child_process');
require('dotenv').config({ path: path.join(__dirname, '.env') });

const { publishVideoToFacebook } = require('./facebook_publisher');
const { publishReelToInstagram } = require('./instagram_publisher');
const { publishVideoToTikTok } = require('./tiktok_publisher');
const { publishVideoToYouTube } = require('./youtube_publisher');

const VIDEOS_DIR = path.join(__dirname, 'videos');
const ALLOWED_VIDEOS = [
  '01_mario_galaxy.mp4',
  '02_rey_steve_minecraft_gratis.mp4',
  '03_mario_referidos_20.mp4'
];

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
      .filter(f => ALLOWED_VIDEOS.includes(f))
      .sort();
    if (mp4Files.length > 0) {
      // Rotación determinística en 3 turnos diarios (bloques de 8 horas) para publicar los 3 videos oficiales cada día
      const slotIndex = Math.floor(Date.now() / (8 * 3600 * 1000)) % mp4Files.length;
      const chosen = mp4Files[slotIndex];
      console.log(`🎬 Videos oficiales en videos/: [${mp4Files.join(', ')}] -> Seleccionado: ${chosen}`);
      return path.join(VIDEOS_DIR, chosen);
    }
  }

  return path.join(VIDEOS_DIR, '01_mario_galaxy.mp4');
}

/**
 * Genera una copia temporal con huella digital (MD5 + pHash visual/acústico) 100% nueva
 * para evitar que TikTok, Instagram Reels, Facebook y YouTube Shorts congelen el video en 0 vistas por duplicado.
 */
function createFreshVideoFingerprint(srcPath) {
  try {
    const outDir = path.join(__dirname, 'out');
    fs.mkdirSync(outDir, { recursive: true });
    const stamp = Date.now();
    const freshPath = path.join(outDir, `fresh_${stamp}_${path.basename(srcPath)}`);
    // Variación sutil e imperceptible al ojo humano: zoom 1.01x-1.02x + micro-ajuste de contraste/brillo + metadatos limpios
    const brightness = ((stamp % 5) - 2) * 0.004; // -0.008 a +0.008
    const contrast = 1.0 + ((stamp % 3) + 1) * 0.005; // 1.005 a 1.015
    const vf = `scale=732:1300,crop=720:1280,eq=brightness=${brightness.toFixed(4)}:contrast=${contrast.toFixed(4)}`;
    execFileSync(
      'ffmpeg',
      [
        '-y',
        '-i',
        srcPath,
        '-map_metadata',
        '-1',
        '-vf',
        vf,
        '-af',
        'volume=1.005',
        '-c:v',
        'libx264',
        '-preset',
        'veryfast',
        '-crf',
        '21',
        '-pix_fmt',
        'yuv420p',
        '-c:a',
        'aac',
        '-b:a',
        '128k',
        '-movflags',
        '+faststart',
        freshPath
      ],
      { stdio: 'ignore' }
    );
    if (fs.existsSync(freshPath) && fs.statSync(freshPath).size > 50000) {
      console.log(`✨ Huella digital renovada (anti-duplicado): ${path.basename(freshPath)}`);
      return freshPath;
    }
  } catch (err) {
    console.warn(`⚠️ Aviso ffmpeg anti-duplicado (${err.message}), usando archivo original.`);
  }
  return srcPath;
}

const RAW_VIDEO_PATH = resolveVideoPath();
const VIDEO_PATH = createFreshVideoFingerprint(RAW_VIDEO_PATH);
const IS_MINECRAFT_VIDEO = /steve|minecraft/i.test(path.basename(RAW_VIDEO_PATH));
const IS_REFERIDOS_VIDEO = /referidos|socios/i.test(path.basename(RAW_VIDEO_PATH));

// Ligas oficiales que SIEMPRE van en los campos de texto de las redes sociales
const LINKS = {
  mainSite: 'https://dreamcrafters.lat',
  sociosSite: 'https://dreamcrafters.lat/socios',
  minecraftDemo: 'https://dreamcrafters.lat/invitacionminecraft/ian-level8',
  marioDemo: 'https://dreamcrafters.lat/invitacionmario/index.html',
  agentesDemo: 'https://dreamcrafters.lat/agentes_de_luz',
  tctSite: 'https://talentocontarifa.lat'
};

const DREAMCRAFTERS_TITLE = IS_REFERIDOS_VIDEO
  ? '💰🍄 ¿Y si en vez de pagar publicidad, te pagamos a ti? ¡Gana el 20% por recomendar DreamCrafters! 🎮'
  : IS_MINECRAFT_VIDEO
  ? '👑⚔️ ¡Crea GRATIS tu invitación interactiva de Minecraft! | DreamCrafters'
  : '🍄✨ ¡Combo 2 en 1 por $100 MXN: Invitación Videojuego + Video Saludo Personalizado de Mario! 🎮 | DreamCrafters';

const DREAMCRAFTERS_CAPTION = IS_REFERIDOS_VIDEO
  ? [
      '💰🍄 ¿Y si en vez de pagarle publicidad a las redes sociales, te pagamos ese dinero directamente a ti?',
      '',
      'En DreamCrafters creamos invitaciones que son videojuegos reales en el celular. Cuando una mamá la manda al grupo de WhatsApp del salón, ¡todas las demás quieren una igual para su fiesta! 🎮🌟',
      '',
      '🔥 PROGRAMA DE SOCIOS DREAMCRAFTERS (20% DIRECTO):',
      '1️⃣ Entra y genera tu enlace único en 30 segundos.',
      '2️⃣ Registra tu CLABE o tarjeta donde quieres recibir tus depósitos.',
      '3️⃣ Por cada invitación comprada desde tu link, ¡te transferimos el 20% directo vía SPEI, sin preguntas!',
      '',
      `👉 Genera tu link del 20% gratis aquí: ${LINKS.sociosSite}`,
      `🌐 Catálogo de mundos interactivos: ${LINKS.mainSite}`,
      `🕹️ Juega el demo de Super Mario Galaxy: ${LINKS.marioDemo}`,
      '',
      '#DreamCrafters #FiestasInfantiles #InvitacionesDigitales #IngresosExtra #MamasEmprendedoras #SalonesDeFiestas #SuperMarioGalaxy'
    ].join('\n')
  : IS_MINECRAFT_VIDEO
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
      `💰 Gana el 20% recomendando: ${LINKS.sociosSite}`,
      '',
      '#DreamCrafters #MinecraftParty #InvitacionesDigitales #FiestasInfantiles #InvitacionesMinecraft #CumpleañosMinecraft'
    ].join('\n')
  : [
      '🍄 ¿Te imaginas que yo mismo felicite a tu peque por su nombre e invite a todos sus amigos? ¡En DreamCrafters te llevas el Combo 2 en 1 de Super Mario Galaxy por solo $100 MXN! 🎮🌟',
      '',
      '1️⃣ Primero: Tus invitados abren tu link, saltan por el espacio y atrapan las 3 Super Estrellas en un minijuego 3D real.',
      '2️⃣ Segundo: ¡Desbloquean la invitación con un VIDEO PERSONALIZADO donde Mario saluda a tu peque por su nombre, dice cuántos años cumple, la fecha de la fiesta y muestra la dirección en pantalla!',
      '📍 Incluye Mapa GPS en Google Maps y confirmación en 1 toque a tu WhatsApp.',
      '',
      '🔥 PROMO LANZAMIENTO: ¡De $250 a solo $100 MXN con entrega inmediata!',
      `👉 Pídela y personalízala en 1 minuto: ${LINKS.mainSite}`,
      `🕹️ Juega el demo y mira el video saludo en vivo: ${LINKS.marioDemo}`,
      `💰 Gana el 20% recomendando: ${LINKS.sociosSite}`,
      '',
      '#DreamCrafters #SuperMarioGalaxy #InvitacionesDigitales #FiestasInfantiles #InvitacionesMario #CumpleañosMarioBros #VideoSaludoMario'
    ].join('\n');

const TCT_CROSSPROMO_TITLE = IS_REFERIDOS_VIDEO
  ? '💰🚀 ¿Y si en vez de pagar publicidad, te pagamos el 20% a ti? | Programa de Socios DreamCrafters'
  : IS_MINECRAFT_VIDEO
  ? '👑⚔️ ¡Regalamos invitaciones interactivas de Minecraft que se juegan en el celular! | DreamCrafters'
  : '🚀 ¡Combo 2 en 1 por $100 MXN: Invitación Videojuego + Video Saludo Personalizado de Mario! 🎮🌟 | DreamCrafters';

const TCT_CROSSPROMO_CAPTION = IS_REFERIDOS_VIDEO
  ? [
      '💰🍄 ¿Y si en vez de pagarle publicidad a las redes, te pagamos el 20% directamente a ti?',
      '',
      'Con el Programa de Socios de DreamCrafters, por cada invitación videojuego que compren desde tu enlace personal en grupos de mamás, colegios o salones de fiestas, recibes el 20% de comisión directa vía SPEI 🎮🌟',
      '',
      `👉 Activa tu link y registra tu CLABE en 30 segundos: ${LINKS.sociosSite}`,
      `🌐 Ver catálogo de invitaciones jugables: ${LINKS.mainSite}`,
      `🕹️ Demo Super Mario Galaxy: ${LINKS.marioDemo}`,
      `⚡ Impulsado por Talento con Tarifa: ${LINKS.tctSite}`,
      '',
      '#DreamCrafters #TalentoConTarifa #FiestasInfantiles #InvitacionesDigitales #Afiliados #IngresosExtra #SuperMarioGalaxy #Reels #Shorts'
    ].join('\n')
  : IS_MINECRAFT_VIDEO
  ? [
      '👑⚔️ ¿Tienes fiesta en puerta? En DreamCrafters liberamos GRATIS el creador de invitaciones interactivas de Minecraft.',
      '',
      'Tus invitados derrotan al Enderman desde su celular para desbloquear la ubicación GPS, cuenta regresiva y confirmación directa a tu WhatsApp 🎮✨',
      '',
      `👉 Crea la tuya gratis aquí: ${LINKS.mainSite}`,
      `🗡️ Juega el demo: ${LINKS.minecraftDemo}`,
      `💰 Gana el 20% recomendando: ${LINKS.sociosSite}`,
      `⚡ Impulsado por Talento con Tarifa: ${LINKS.tctSite}`,
      '',
      '#DreamCrafters #Minecraft #InvitacionesDigitales #FiestasInfantiles #TalentoConTarifa #Reels #Shorts'
    ].join('\n')
  : [
      '🍄 ¡Mamma mia! En DreamCrafters armamos el Combo 2 en 1 definitivo de Super Mario Galaxy por solo $100 MXN 🎮🌟',
      '',
      '1️⃣ Tus invitados juegan en su celular atrapando las 3 Super Estrellas en gravedad cero.',
      '2️⃣ ¡Al ganar desbloquean la invitación con un VIDEO PERSONALIZADO donde Mario felicita al cumpleañero por su nombre, dice cuántos años cumple, la fecha y la dirección del salón, más mapa GPS y confirmación a WhatsApp!',
      '',
      '🔥 PROMO LANZAMIENTO: ¡De $250 a solo $100 MXN con entrega inmediata!',
      `👉 Personalízala al instante aquí: ${LINKS.mainSite}`,
      `🕹️ Juega el demo con video saludo: ${LINKS.marioDemo}`,
      `💰 Gana el 20% recomendando: ${LINKS.sociosSite}`,
      '',
      '─────────────────────────',
      '🤖 Desarrollo interactivo y automatización con IA impulsado por Talento con Tarifa.',
      `⚡ Digitaliza o automatiza tu negocio hoy: ${LINKS.tctSite}`,
      '',
      '#DreamCrafters #TalentoConTarifa #SuperMarioGalaxy #InvitacionesDigitales #FiestasInfantiles #SuperMarioBros #Reels #Shorts'
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
    selected_video: path.basename(VIDEO_PATH),
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

  const localTikTokBridge = path.resolve(__dirname, '..', 'krauge', 'krauge_tiktok_autopost.py');
  if (fs.existsSync(localTikTokBridge)) {
    try {
      const { execFileSync } = require('child_process');
      console.log('🎵 Publicando directo a Público en TikTok Studio Web (puente local)...');
      execFileSync('python', [localTikTokBridge, '--force-dc-video', path.basename(VIDEO_PATH)], {
        stdio: 'inherit'
      });
      results.talento_con_tarifa.tiktok = {
        success: true,
        mode: 'TIKTOK_STUDIO_LOCAL',
        video: path.basename(VIDEO_PATH)
      };
    } catch (err) {
      console.error('⚠️ Error en puente local TikTok Studio:', err.message);
      results.talento_con_tarifa.tiktok = { success: false, error: err.message };
    }
  } else if (process.env.TIKTOK_REFRESH_TOKEN && process.env.TIKTOK_CLIENT_KEY) {
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
        title: IS_REFERIDOS_VIDEO
          ? '💰🍄 ¿Y si en vez de pagar publicidad, te pagamos el 20% a ti? | Socios DreamCrafters #Shorts'
          : IS_MINECRAFT_VIDEO
          ? '👑⚔️ ¡Invitación interactiva GRATIS de Minecraft! | DreamCrafters #Shorts'
          : '🍄 ¡Combo 2 en 1 por $100: Invitación Videojuego + Video Saludo de Mario! 🎮 | DreamCrafters #Shorts',
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
