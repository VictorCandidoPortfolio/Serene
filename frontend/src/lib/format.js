/** Vocabulário do motor, espelhando app/engine/axes.py do backend. */

// `dica` traduz o eixo para o vocabulário da aula (frescor, profundidade...).
export const EIXOS = [
  { chave: 'v1', nome: 'Temperatura', baixo: 'fresco', alto: 'quente', dica: 'Sensação: do frescor (0) ao calor (10).' },
  { chave: 'v2', nome: 'Profundidade', baixo: 'leve', alto: 'profundo', dica: 'Peso e persistência na pele.' },
  { chave: 'v3', nome: 'Doçura', baixo: 'seco', alto: 'doce', dica: 'Do seco (0) ao doce (10).' },
  { chave: 'v4', nome: 'Intensidade', baixo: 'discreto', alto: 'marcante', dica: 'Presença: o quanto se faz notar.' },
  { chave: 'v5', nome: 'Complexidade', baixo: 'simples', alto: 'complexo', dica: 'Estrutura: uma faceta ou muitas.' },
  { chave: 'v6', nome: 'Floralidade', baixo: 'não floral', alto: 'floral', dica: 'O quanto lembra flores.' },
];

export const CAMADAS = [
  { chave: 'saida', nome: 'Saída' },
  { chave: 'coracao', nome: 'Coração' },
  { chave: 'fundo', nome: 'Fundo' },
];

export const PESOS = [
  { chave: 'pouco', nome: 'Pouco', valor: 1 },
  { chave: 'medio', nome: 'Médio', valor: 2 },
  { chave: 'bastante', nome: 'Bastante', valor: 3 },
];

export const NOME_PESO = { 1: 'Pouco', 2: 'Médio', 3: 'Bastante', pouco: 'Pouco', medio: 'Médio', bastante: 'Bastante' };

export const STATUS = {
  rascunho: 'Rascunho',
  em_ajuste: 'Em ajuste',
  aprovada: 'Aprovada',
  arquivada: 'Arquivada',
};

/** Rótulos dos valores enumerados que a API devolve sem acento. */
const ROTULOS = {
  media: 'Média', alta: 'Alta', baixa: 'Baixa',
  tecnico: 'Técnico', informado: 'Informado', inferido: 'Inferido', estimado: 'Estimado',
  simples: 'Simples', composta: 'Composta', desconhecida: 'Desconhecida',
};

export function rotulo(valor) {
  return ROTULOS[valor] || valor || '—';
}

/** Número de eixo com uma casa decimal, ou "—" quando o motor não sabe. */
export function num(v) {
  return v === null || v === undefined ? '—' : Number(v).toFixed(1).replace('.', ',');
}

export function pct(v) {
  return v === null || v === undefined ? '—' : `${Math.round(v * 100)}%`;
}

export function data(iso) {
  if (!iso) return '';
  return new Date(iso).toLocaleDateString('pt-BR', { day: 'numeric', month: 'long', year: 'numeric' });
}

/** "fresco" / "quente" conforme o lado da escala 0–10. */
export function leituraEixo(chave, v) {
  if (v === null || v === undefined) return 'sem dado';
  const eixo = EIXOS.find((e) => e.chave === chave);
  if (!eixo) return '';
  if (v < 4) return eixo.baixo;
  if (v > 6) return eixo.alto;
  return 'equilibrado';
}

/** "serenidade" → "Serenidade" (chaves de regra viram nomes de exibição). */
export function capitalizar(txt) {
  return txt ? txt.charAt(0).toUpperCase() + txt.slice(1) : txt;
}

/** Sensação (fresca / neutra / quente) a partir da temperatura. */
export function sensacao(v1) {
  if (v1 === null || v1 === undefined) return null;
  if (v1 < 4) return 'Fresca';
  if (v1 > 6) return 'Quente';
  return 'Neutra';
}

/** Vírgula decimal e sinal, para diferenças entre versões ("+1,5"). */
export function delta(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return '—';
  const s = Math.abs(v).toFixed(1).replace('.', ',');
  return v > 0 ? `+${s}` : v < 0 ? `−${s}` : '0';
}

/** Camada da pirâmide com maior afinidade, para resumir o papel de uma essência. */
export function camadaDominante(papel) {
  if (!papel) return null;
  const [chave] = Object.entries(papel).sort((a, b) => b[1] - a[1])[0] || [];
  return CAMADAS.find((c) => c.chave === chave)?.nome ?? null;
}

export function normalizar(txt) {
  return (txt || '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .trim();
}
