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
  '01_fortnite_juego_150_hombre.mp4',
  '02_rey_steve_minecraft_gratis.mp4',
  '03_fortnite_afiliados_20_hombre.mp4',
  '04_fortnite_juego_150_mujer.mp4',
  '05_fortnite_afiliados_20_mujer.mp4',
  '06_volver_al_futuro_juego_150.mp4',
  '07_volver_al_futuro_afiliados_20.mp4'
];

function selectVideoByUtcSchedule(mp4Files) {
  const utcHour = new Date().getUTCHours();
  // Mapeo determinístico de los turnos diarios (UTC):
  // - 13:30 UTC (08:30 AM Cancún): 06_volver_al_futuro_juego_150.mp4 (Volver al Futuro 88 MPH $150)
  // - 15:30 UTC (10:30 AM Cancún): 07_volver_al_futuro_afiliados_20.mp4 (Volver al Futuro Afiliados 20%)
  // - 17:30 UTC (12:30 PM Cancún): 01_fortnite_juego_150_hombre.mp4
  // - 19:30 UTC (02:30 PM Cancún): 03_fortnite_afiliados_20_hombre.mp4
  // - 21:30 UTC (04:30 PM Cancún): 04_fortnite_juego_150_mujer.mp4
  // - 23:30 UTC (06:30 PM Cancún): 05_fortnite_afiliados_20_mujer.mp4
  // - 02:00 UTC (09:00 PM Cancún): 02_rey_steve_minecraft_gratis.mp4
  let preferred = '06_volver_al_futuro_juego_150.mp4';
  if (utcHour >= 12 && utcHour < 15) {
    preferred = '06_volver_al_futuro_juego_150.mp4';
  } else if (utcHour >= 15 && utcHour < 17) {
    preferred = '07_volver_al_futuro_afiliados_20.mp4';
  } else if (utcHour >= 17 && utcHour < 19) {
    preferred = '01_fortnite_juego_150_hombre.mp4';
  } else if (utcHour >= 19 && utcHour < 21) {
    preferred = '03_fortnite_afiliados_20_hombre.mp4';
  } else if (utcHour >= 21 && utcHour < 23) {
    preferred = '04_fortnite_juego_150_mujer.mp4';
  } else if (utcHour >= 23 || utcHour < 1) {
    preferred = '05_fortnite_afiliados_20_mujer.mp4';
  } else {
    preferred = '02_rey_steve_minecraft_gratis.mp4';
  }
  if (mp4Files.includes(preferred)) {
    return preferred;
  }
  const slotIndex = Math.floor(Date.now() / (3 * 3600 * 1000)) % mp4Files.length;
  return mp4Files[slotIndex];
}

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
      const chosen = selectVideoByUtcSchedule(mp4Files);
      console.log(`🎬 Videos oficiales en videos/: [${mp4Files.join(', ')}] -> Seleccionado: ${chosen}`);
      return path.join(VIDEOS_DIR, chosen);
    }
  }

  return path.join(VIDEOS_DIR, '01_fortnite_juego_150_hombre.mp4');
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
    const brightness = ((stamp % 5) - 2) * 0.004;
    const contrast = 1.0 + ((stamp % 3) + 1) * 0.005;
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

const IS_CHECK_ONLY = process.argv.includes('--check-config');
const RAW_VIDEO_PATH = resolveVideoPath();
const VIDEO_PATH = IS_CHECK_ONLY ? RAW_VIDEO_PATH : createFreshVideoFingerprint(RAW_VIDEO_PATH);
const RAW_BASENAME = path.basename(RAW_VIDEO_PATH);
const IS_MINECRAFT_VIDEO = /steve|minecraft/i.test(RAW_BASENAME);
const IS_REFERIDOS_VIDEO = /referidos|socios|afiliados/i.test(RAW_BASENAME);
const IS_FORTNITE_VIDEO = /fortnite/i.test(RAW_BASENAME);
const IS_BTTF_VIDEO = /volver_al_futuro|bttf|marty|delorean/i.test(RAW_BASENAME);
const IS_MUJER_VIDEO = /mujer|bomber/i.test(RAW_BASENAME);

// Ligas oficiales que SIEMPRE van en los campos de texto de las redes sociales
const LINKS = {
  mainSite: 'https://dreamcrafters.lat',
  sociosSite: 'https://dreamcrafters.lat/socios',
  bttfDemo: 'https://dreamcrafters.lat/invitacionvolveralfuturo/index.html',
  fortniteDemo: 'https://dreamcrafters.lat/invitacionfortnite/index.html',
  minecraftDemo: 'https://dreamcrafters.lat/invitacionminecraft/ian-level8',
  marioDemo: 'https://dreamcrafters.lat/invitacionmario/index.html',
  agentesDemo: 'https://dreamcrafters.lat/agentes_de_luz',
  tctSite: 'https://talentocontarifa.lat'
};

const DREAMCRAFTERS_TITLE = IS_REFERIDOS_VIDEO
  ? '💰⚡ ¿Y si en vez de pagar publicidad, te pagamos el 20% a ti vía SPEI? ¡Programa de Socios DreamCrafters! 🎮✨'
  : IS_MINECRAFT_VIDEO
  ? '👑⚔️ ¡Crea GRATIS tu invitación interactiva de Minecraft! | DreamCrafters'
  : IS_BTTF_VIDEO
  ? '🚗⚡ ¡Combo 2 en 1 de Volver al Futuro 88 MPH por $150 MXN: Cabina DeLorean 360° + Video Saludo de Marty McFly! 🔥⏳'
  : IS_FORTNITE_VIDEO
  ? '🦙💥 ¡Combo 2 en 1 de Fortnite Battle Royale por $150 MXN: Invitación Videojuego 3D + Video Saludo Personalizado! 🎮🏆'
  : '🍄✨ ¡Combo 2 en 1 por $100 MXN: Invitación Videojuego + Video Saludo Personalizado de Mario! 🎮 | DreamCrafters';

const DREAMCRAFTERS_CAPTION = IS_REFERIDOS_VIDEO
  ? [
      '💰⚡ ¿Y si en vez de pagarle publicidad a las redes sociales, te pagamos ese 20% directamente a ti en tu cuenta bancaria?',
      '',
      'En DreamCrafters creamos invitaciones que son videojuegos reales en el celular (como nuestra nueva misión de Volver al Futuro acelerando el DeLorean a 88 MPH en 360° y Fortnite Battle Royale con Piñata 3D). Cuando una mamá la manda al grupo de WhatsApp del salón, ¡todas las demás quieren una igual para su fiesta! 🚗⚡🎮',
      '',
      '🔥 PROGRAMA DE SOCIOS DREAMCRAFTERS (20% DIRECTO VÍA SPEI):',
      '1️⃣ Entra y genera tu enlace único en 30 segundos (100% gratis).',
      '2️⃣ Registra tu CLABE donde quieres recibir tus ganancias.',
      '3️⃣ Por cada invitación que compren desde tu link en grupos de mamás, colegios o salones de fiestas, ¡recibes el 20% directo vía SPEI, sin topes!',
      '',
      `👉 Genera tu link del 20% gratis aquí: ${LINKS.sociosSite}`,
      `🚗 Juega el nuevo demo de Volver al Futuro 88 MPH: ${LINKS.bttfDemo}`,
      `🌐 Catálogo de invitaciones jugables: ${LINKS.mainSite}`,
      '',
      '#DreamCrafters #VolverAlFuturo #BackToTheFuture #DeLorean #FiestasInfantiles #InvitacionesDigitales #IngresosExtra #MamasEmprendedoras'
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
  : IS_BTTF_VIDEO
  ? [
      '🚗⚡ ¡Santos protones! ¿Te imaginas que Marty McFly invite a todos los amigos de tu peque a viajar en el tiempo a su fiesta? ¡Conoce la nueva Invitación Interactiva 2 en 1 de Volver al Futuro: 88 MPH por solo $150 MXN! 🔥⏳',
      '',
      '1️⃣ Primero: Tus invitados abren el link en su celular, entran a la cabina 360° del DeLorean y tocan la pantalla para acelerar hasta 88 MPH (1.21 Gigawatts) saltando por el túnel del tiempo 💥✨',
      '2️⃣ Segundo: ¡Aterrizan en la fiesta y desbloquean el Cuadro de Saludo en Video HD de Marty McFly, el Tablero de Circuitos del Tiempo, el Mapa GPS y descargan su Placa California VIP personalizada antes de confirmar asistencia a tu WhatsApp!',
      '',
      '🔥 PROMO LANZAMIENTO: ¡Combo 2 en 1 (Cabina 360° DeLorean + Video Saludo de Marty) por solo $150 MXN!',
      `👉 Pídela y personalízala hoy en: ${LINKS.mainSite}`,
      `🚗 Juega el demo del DeLorean a 88 MPH en vivo: ${LINKS.bttfDemo}`,
      `💰 Gana el 20% recomendando en grupos de mamás: ${LINKS.sociosSite}`,
      '',
      '#DreamCrafters #VolverAlFuturo #BackToTheFuture #MartyMcFly #DeLorean #InvitacionesDigitales #FiestasInfantiles #CumpleañosTematico'
    ].join('\n')
  : [
      `🪂🦙 ¡Atención escuadrón! ¿Te imaginas que ${IS_MUJER_VIDEO ? 'Brite Bomber' : 'el Capitán Jonesy'} convoque a todos los amigos de tu peque a su fiesta? ¡Conoce la nueva Invitación Videojuego 2 en 1 de Fortnite Battle Royale por solo $150 MXN! 🎮🏆`,
      '',
      '1️⃣ Primero: Tus invitados abren el link en su celular, saltan del Autobús de Batalla y disparan con mira táctica hasta reventar la Piñata Llama 3D en una Grieta Dimensional épica de ¡VICTORIA MAGISTRAL! 💥✨',
      '2️⃣ Segundo: ¡Desbloquean las transmisiones secretas en video, el Mapa GPS del Punto de Caída, la cuenta regresiva de La Tormenta y descargan su Pase de Batalla VIP personalizado con su nombre antes de confirmar asistencia a tu WhatsApp!',
      '',
      '🔥 PROMO LANZAMIENTO: ¡Combo 2 en 1 (Videojuego Interactivo + Video Saludo) por solo $150 MXN!',
      `👉 Pídela y personalízala hoy en: ${LINKS.mainSite}`,
      `🕹️ Juega el demo de Fortnite y mira el video saludo en vivo: ${LINKS.fortniteDemo}`,
      `💰 Gana el 20% recomendando en grupos de mamás: ${LINKS.sociosSite}`,
      '',
      '#DreamCrafters #Fortnite #FortniteBattleRoyale #CumpleañosFortnite #InvitacionesFortnite #InvitacionesDigitales #FiestasInfantiles #VictoriaMagistral'
    ].join('\n');

const TCT_CROSSPROMO_TITLE = IS_REFERIDOS_VIDEO
  ? '💰⚡ ¿Y si en vez de pagar publicidad, te pagamos el 20% vía SPEI a ti? | Programa de Socios DreamCrafters'
  : IS_MINECRAFT_VIDEO
  ? '👑⚔️ ¡Regalamos invitaciones interactivas de Minecraft que se juegan en el celular! | DreamCrafters'
  : IS_BTTF_VIDEO
  ? '🚗⚡ ¡Invitación Interactiva 360° de Volver al Futuro (88 MPH) + Saludo de Marty McFly por $150 MXN! 🔥⏳ | DreamCrafters'
  : '🦙💥 ¡Invitación Videojuego 3D de Fortnite Battle Royale + Pase de Batalla VIP por $150 MXN! 🎮🏆 | DreamCrafters';

const TCT_CROSSPROMO_CAPTION = IS_REFERIDOS_VIDEO
  ? [
      '💰⚡ ¿Y si en vez de pagarle publicidad a las redes, te pagamos el 20% directamente a ti vía SPEI?',
      '',
      'Con el Programa de Socios de DreamCrafters, por cada invitación videojuego (como la nueva de Volver al Futuro 88 MPH en cabina 360° o Fortnite Battle Royale) que compren desde tu enlace personal en grupos de mamás, colegios o salones de fiestas, recibes el 20% de comisión directa vía SPEI 🚗⚡🏆',
      '',
      `👉 Activa tu link y registra tu CLABE en 30 segundos: ${LINKS.sociosSite}`,
      `🚗 Juega el demo de Volver al Futuro 88 MPH: ${LINKS.bttfDemo}`,
      `🌐 Ver catálogo de invitaciones jugables: ${LINKS.mainSite}`,
      `⚡ Impulsado por Talento con Tarifa: ${LINKS.tctSite}`,
      '',
      '#DreamCrafters #TalentoConTarifa #VolverAlFuturo #BackToTheFuture #FiestasInfantiles #InvitacionesDigitales #Afiliados #IngresosExtra #Reels #Shorts'
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
  : IS_BTTF_VIDEO
  ? [
      '🚗⚡ ¡Viaja a 88 MPH en la fiesta de tu peque! En DreamCrafters lanzamos el Combo 2 en 1 de Volver al Futuro: 88 MPH con Marty McFly por solo $150 MXN 🔥⏳',
      '',
      '1️⃣ Tus invitados abren el link en su celular, entran a la cabina 360° del DeLorean y aceleran hasta 88 MPH con 1.21 Gigawatts.',
      '2️⃣ ¡Al saltar en el tiempo desbloquean el Cuadro de Saludo en Video de Marty McFly, los Circuitos del Tiempo, el Mapa GPS y descargan su Placa California VIP antes de confirmar a tu WhatsApp!',
      '',
      '🔥 PROMO LANZAMIENTO: ¡Combo 2 en 1 por solo $150 MXN!',
      `👉 Personalízala al instante aquí: ${LINKS.mainSite}`,
      `🚗 Juega el demo con cabina 360° en vivo: ${LINKS.bttfDemo}`,
      `💰 Gana el 20% recomendando vía SPEI: ${LINKS.sociosSite}`,
      '',
      '─────────────────────────',
      '🤖 Desarrollo interactivo y automatización con IA impulsado por Talento con Tarifa.',
      `⚡ Digitaliza o automatiza tu negocio hoy: ${LINKS.tctSite}`,
      '',
      '#DreamCrafters #TalentoConTarifa #VolverAlFuturo #BackToTheFuture #DeLorean #InvitacionesDigitales #FiestasInfantiles #Reels #Shorts'
    ].join('\n')
  : [
      `🪂🦙 ¡Victoria Magistral en la fiesta de tu peque! En DreamCrafters lanzamos el Combo 2 en 1 de Fortnite Battle Royale (${IS_MUJER_VIDEO ? 'Edición Brite Bomber' : 'Edición Capitán Jonesy'}) por solo $150 MXN 🎮🏆`,
      '',
      '1️⃣ Tus invitados abren el link en su celular, saltan del Autobús de Batalla y disparan con mira táctica hasta romper la Piñata Llama 3D en una Grieta Dimensional épica.',
      '2️⃣ ¡Al lograr la Victoria Magistral desbloquean el Video Saludo, el Mapa GPS del Punto de Caída y descargan su propio Pase de Batalla VIP personalizado antes de confirmar a tu WhatsApp!',
      '',
      '🔥 PROMO LANZAMIENTO: ¡Combo 2 en 1 por solo $150 MXN!',
      `👉 Personalízala al instante aquí: ${LINKS.mainSite}`,
      `🕹️ Juega el demo con video saludo en vivo: ${LINKS.fortniteDemo}`,
      `💰 Gana el 20% recomendando vía SPEI: ${LINKS.sociosSite}`,
      '',
      '─────────────────────────',
      '🤖 Desarrollo interactivo y automatización con IA impulsado por Talento con Tarifa.',
      `⚡ Digitaliza o automatiza tu negocio hoy: ${LINKS.tctSite}`,
      '',
      '#DreamCrafters #TalentoConTarifa #Fortnite #FortniteBattleRoyale #InvitacionesDigitales #FiestasInfantiles #CumpleañosFortnite #Reels #Shorts'
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
    raw_video: RAW_BASENAME,
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
      console.log('🎵 Publicando directo a Público en TikTok Studio Web (puente local)...');
      execFileSync('python', [localTikTokBridge, '--force-dc-video', RAW_BASENAME], {
        stdio: 'inherit'
      });
      results.talento_con_tarifa.tiktok = {
        success: true,
        mode: 'TIKTOK_STUDIO_LOCAL',
        video: RAW_BASENAME
      };
    } catch (err) {
      console.error('⚠️ Error en puente local TikTok Studio:', err.message);
      results.talento_con_tarifa.tiktok = { success: false, error: err.message };
    }
  } else if (process.env.TIKTOK_REFRESH_TOKEN && process.env.TIKTOK_CLIENT_KEY) {
    try {
      results.talento_con_tarifa.tiktok = await publishVideoToTikTok(VIDEO_PATH, {
        title: `${DREAMCRAFTERS_TITLE} 👉 ${LINKS.mainSite} | Socios 20%: ${LINKS.sociosSite} #DreamCrafters #Fortnite #FortniteBattleRoyale #TalentoConTarifa`
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
          ? '💰⚡ ¿Y si en vez de pagar publicidad, te pagamos el 20% vía SPEI? | Socios DreamCrafters #Shorts'
          : IS_MINECRAFT_VIDEO
          ? '👑⚔️ ¡Invitación interactiva GRATIS de Minecraft! | DreamCrafters #Shorts'
          : IS_BTTF_VIDEO
          ? '🚗⚡ ¡Combo 2 en 1 de Volver al Futuro 88 MPH por $150 MXN: Cabina 360° + Marty McFly! #Shorts'
          : '🦙💥 ¡Combo 2 en 1 de Fortnite Battle Royale por $150 MXN: Invitación Videojuego 3D! 🎮🏆 #Shorts',
        description: TCT_CROSSPROMO_CAPTION,
        tags: [
          'DreamCrafters',
          'Invitaciones Digitales',
          'Volver al Futuro',
          'Back to the Future',
          'Fortnite',
          'Fortnite Battle Royale',
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
