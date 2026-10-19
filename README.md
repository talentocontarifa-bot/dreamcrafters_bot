# ✨ Dreamcrafters — Credenciales y Publicadores Oficiales

Directorio de accesos y módulos de publicación para **Dreamcrafters - Invitaciones Virtuales IA**.

## 🔐 Credenciales Activas ([`.env`](.env))

- **`META_PAGE_ID`**: `539086392630917` (*Dreamcrafters - Invitaciones Virtuales IA*)
- **`META_PAGE_ACCESS_TOKEN`**: Token de página **perpetuo (`expires_at: 0`, nunca caduca)** con los permisos completos:
  - `pages_show_list`
  - `pages_read_engagement`
  - `pages_manage_posts`
  - `business_management`
  - `instagram_basic`
  - `instagram_content_publish`
- **`INSTAGRAM_ACCOUNT_ID`**: Se autocompleta automáticamente al correr `node dreamcrafter/check_tokens.js` en cuanto la cuenta de Instagram de Dreamcrafters quede vinculada a la página de Facebook (no requiere generar nuevo token).

## 📦 Módulos Disponibles

- [`facebook_publisher.js`](facebook_publisher.js):
  - `publishVideoToFacebook(videoFilePath, { title, description })`: Sube Reels (`/{pageId}/video_reels`) con fallback automático a `/{pageId}/videos`.
  - `publishPostToFacebook(message, link)`: Publica en el feed de la página.
- [`instagram_publisher.js`](instagram_publisher.js):
  - `publishReelToInstagram(videoFilePath, { caption, share_to_feed })`: Publica Reels en Instagram (auto-detecta el `INSTAGRAM_ACCOUNT_ID` desde `META_PAGE_ID` si aún no está en `.env`).
- [`check_tokens.js`](check_tokens.js):
  - Verifica en vivo el estado del token perpetuo de Facebook y detecta si Instagram ya fue vinculado.
