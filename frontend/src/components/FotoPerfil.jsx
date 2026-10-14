import { useEffect, useState } from 'react';

/** "Ana Maria Souza" → "AS". */
export function iniciais(nome) {
  const partes = (nome || '?').trim().split(/\s+/);
  const letras = partes.length > 1 ? [partes[0], partes[partes.length - 1]] : partes;
  return letras.map((p) => p[0]?.toUpperCase() ?? '').join('');
}

/**
 * Avatar redondo da usuária: a foto do Cloudinary, ou as iniciais quando não
 * há foto (ou quando ela não carrega). `src` substitui a foto salva — é a
 * prévia da imagem escolhida antes de enviar.
 */
export default function FotoPerfil({ user, src, tamanho = 46, className = '' }) {
  const endereco = src || user?.foto_url;
  const [falhou, setFalhou] = useState(false);
  useEffect(() => setFalhou(false), [endereco]);

  return (
    <span
      className={`avatar foto-perfil ${className}`}
      style={{ width: tamanho, height: tamanho, fontSize: Math.round(tamanho * 0.34) }}
      aria-hidden="true"
    >
      {endereco && !falhou ? (
        <img src={endereco} alt="" onError={() => setFalhou(true)} />
      ) : (
        iniciais(user?.nome)
      )}
    </span>
  );
}
