/**
 * Prepara a foto de perfil no navegador antes do envio.
 *
 * Uma foto de celular tem 3–10 MB; a API aceita até 2 MB e o avatar aparece
 * no máximo com ~100px. Então a imagem é cortada em quadrado (centro),
 * reduzida para LADO_FOTO px e convertida em data URI base64 — o formato que
 * a API espera em `PUT /auth/me/foto`. Resultado típico: 30–80 KB.
 *
 * `createImageBitmap` lê o arquivo direto, sem `URL.createObjectURL`: um
 * endereço `blob:` seria bloqueado pela Content-Security-Policy do build.
 */

export const LADO_FOTO = 512;
const ENTRADA_MAX_BYTES = 20 * 1024 * 1024;

/**
 * @param {File} arquivo  o que veio do <input type="file">
 * @returns {Promise<string>} "data:image/webp;base64,..." (ou image/jpeg)
 * @throws {Error} com mensagem legível se o arquivo não servir
 */
export async function prepararFoto(arquivo) {
  if (!arquivo.type.startsWith('image/')) {
    throw new Error('Escolha um arquivo de imagem (JPEG, PNG ou WebP).');
  }
  if (arquivo.size > ENTRADA_MAX_BYTES) {
    throw new Error('Essa imagem é grande demais. Escolha uma de até 20 MB.');
  }

  let bitmap;
  try {
    bitmap = await createImageBitmap(arquivo);
  } catch {
    throw new Error('Não foi possível ler essa imagem. Tente outra em JPEG, PNG ou WebP.');
  }

  const lado = Math.min(bitmap.width, bitmap.height);
  const destino = Math.min(LADO_FOTO, lado);
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = destino;
  const ctx = canvas.getContext('2d');
  // Fundo branco: PNG transparente convertido em JPEG ficaria com fundo preto.
  ctx.fillStyle = '#fff';
  ctx.fillRect(0, 0, destino, destino);
  ctx.imageSmoothingQuality = 'high';
  ctx.drawImage(
    bitmap,
    (bitmap.width - lado) / 2,
    (bitmap.height - lado) / 2,
    lado,
    lado,
    0,
    0,
    destino,
    destino,
  );
  bitmap.close?.();

  // Navegadores sem codificador WebP devolvem PNG (pesado): aí vai JPEG.
  const webp = canvas.toDataURL('image/webp', 0.85);
  return webp.startsWith('data:image/webp') ? webp : canvas.toDataURL('image/jpeg', 0.88);
}
