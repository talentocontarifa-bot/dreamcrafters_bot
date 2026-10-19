/**
 * facebook_publisher.js — Publicador de Videos/Reels y Posts para la página de Facebook de Dreamcrafters
 * Página: "Dreamcrafters - Invitaciones Virtuales IA" (ID: 539086392630917)
 */
const fs = require('fs');
const path = require('path');
let axios;
try {
  axios = require('axios');
} catch (e) {
  axios = require(path.join(__dirname, '..', 'rattle', 'node_modules', 'axios'));
}
let FormData;
try {
  FormData = require('form-data');
} catch (e) {
  FormData = require(path.join(__dirname, '..', 'talento_con_tarifa_bot', 'video_tct', 'node_modules', 'form-data'));
}
require(path.join(__dirname, '..', 'rattle', 'node_modules', 'dotenv')).config({ path: path.join(__dirname, '.env') });

const GRAPH_VERSION = process.env.META_GRAPH_VERSION || 'v21.0';

/**
 * Publica un Reel o Video vertical en la Página de Facebook de Dreamcrafters.
 * Intenta primero el endpoint oficial de Reels (/video_reels) y hace fallback a /videos.
 */
async function publishVideoToFacebook(videoFilePath, { title = '', description = '', pageId: customPageId, accessToken: customToken, label = 'Facebook' } = {}) {
  const pageId = customPageId || process.env.META_PAGE_ID;
  const accessToken = customToken || process.env.META_PAGE_ACCESS_TOKEN;

  if (!pageId || !accessToken) {
    throw new Error(`Faltan credenciales de Facebook (${label}): pageId o accessToken`);
  }
  if (!fs.existsSync(videoFilePath)) {
    throw new Error(`No existe el archivo de video: ${videoFilePath}`);
  }

  const fileSize = fs.statSync(videoFilePath).size;

  // 1. Intentar subida como Facebook Reel (/video_reels)
  try {
    console.log(`📘 [${label} Reels] Iniciando sesión de carga en Meta Graph API (Page ID: ${pageId})...`);
    const startRes = await axios.post(`https://graph.facebook.com/${GRAPH_VERSION}/${pageId}/video_reels`, {
      upload_phase: 'start',
      access_token: accessToken
    });

    const videoId = startRes.data?.video_id;
    const uploadUrl = startRes.data?.upload_url;

    if (videoId && uploadUrl) {
      console.log(`📤 [Facebook Reels] Subiendo binario (${(fileSize / (1024 * 1024)).toFixed(2)} MB)...`);
      const videoBuffer = fs.readFileSync(videoFilePath);
      await axios.post(uploadUrl, videoBuffer, {
        headers: {
          Authorization: `OAuth ${accessToken}`,
          offset: '0',
          file_size: String(fileSize),
          'Content-Type': 'application/octet-stream'
        },
        maxBodyLength: Infinity,
        maxContentLength: Infinity,
        timeout: 300000
      });

      console.log('✅ [Facebook Reels] Binario cargado. Publicando Reel...');
      const finishRes = await axios.post(`https://graph.facebook.com/${GRAPH_VERSION}/${pageId}/video_reels`, null, {
        params: {
          access_token: accessToken,
          video_id: videoId,
          upload_phase: 'finish',
          video_state: 'PUBLISHED',
          description: description || title,
          title: title || undefined
        }
      });

      if (finishRes.data?.success || finishRes.data?.post_id || videoId) {
        console.log(`🎉 [Facebook Reels] ¡Publicado con éxito! Video ID: ${videoId}`);
        return { success: true, mode: 'REEL', id: videoId, postId: finishRes.data?.post_id };
      }
    }
  } catch (reelErr) {
    console.warn(`⚠️ [Facebook Reels] Fallback a /videos (${reelErr.response?.data?.error?.message || reelErr.message})`);
  }

  // 2. Fallback a /{pageId}/videos (Multipart upload)
  console.log('📤 [Facebook Video] Subiendo a /{pageId}/videos...');
  const form = new FormData();
  form.append('access_token', accessToken);
  form.append('description', description || title);
  if (title) form.append('title', title);
  form.append('file', fs.createReadStream(videoFilePath), {
    filename: path.basename(videoFilePath),
    contentType: 'video/mp4'
  });

  const videoRes = await axios.post(`https://graph.facebook.com/${GRAPH_VERSION}/${pageId}/videos`, form, {
    headers: form.getHeaders(),
    maxBodyLength: Infinity,
    maxContentLength: Infinity,
    timeout: 300000
  });

  if (videoRes.data?.id) {
    console.log(`🎉 [Facebook Video] ¡Publicado con éxito! ID: ${videoRes.data.id}`);
    return { success: true, mode: 'VIDEO', id: videoRes.data.id };
  }

  throw new Error('Facebook no devolvió un ID de video válido.');
}

/**
 * Publica un post de texto/enlace en el feed de la Página de Facebook de Dreamcrafters.
 */
async function publishPostToFacebook(message, link = null) {
  const pageId = process.env.META_PAGE_ID;
  const accessToken = process.env.META_PAGE_ACCESS_TOKEN;

  const params = { message, access_token: accessToken };
  if (link) params.link = link;

  const res = await axios.post(`https://graph.facebook.com/${GRAPH_VERSION}/${pageId}/feed`, null, { params });
  return { success: true, id: res.data?.id };
}

module.exports = {
  publishVideoToFacebook,
  publishPostToFacebook
};
