/**
 * Regra de senha forte — espelho de `problemas_da_senha` no backend
 * (backend/app/core/security.py). Aqui ela só serve para mostrar a checklist
 * ao vivo; quem garante a regra é a API, que valida de novo no cadastro.
 */

const encoder = new TextEncoder();

/**
 * Lista os requisitos e se cada um foi atendido.
 * @param {string} senha
 * @returns {{id: string, texto: string, ok: boolean}[]}
 */
export function requisitosSenha(senha) {
  return [
    { id: 'tamanho', texto: 'Pelo menos 8 caracteres', ok: senha.length >= 8 },
    { id: 'maiuscula', texto: 'Uma letra maiúscula', ok: /\p{Lu}/u.test(senha) },
    {
      id: 'numero',
      texto: 'Um número ou caractere especial (! @ # $ %)',
      // Espaço não conta como caractere especial (igual ao backend).
      ok: /\d/.test(senha) || /[^\p{L}\p{N}\s]/u.test(senha),
    },
  ];
}

/** O bcrypt do backend só aceita até 72 bytes (letras acentuadas valem 2). */
export function senhaLongaDemais(senha) {
  return encoder.encode(senha).length > 72;
}

export function senhaForte(senha) {
  return requisitosSenha(senha).every((r) => r.ok) && !senhaLongaDemais(senha);
}
