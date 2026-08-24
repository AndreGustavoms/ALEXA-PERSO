const MAX_TRANSCRIPT_LENGTH = 180;

function normalizeText(value: string) {
  return value
    .normalize('NFD')
    .replace(/[\u0300-\u036f]/g, '')
    .toLowerCase();
}

export function createAssistantReply(transcript: string) {
  const cleanTranscript = transcript.replace(/\s+/g, ' ').trim();
  const normalizedTranscript = normalizeText(cleanTranscript);

  if (/\b(oi|ola|bom dia|boa tarde|boa noite)\b/.test(normalizedTranscript)) {
    return 'Olá! Que bom falar com você. Como posso ajudar?';
  }

  if (/\b(ajuda|o que voce faz|como funciona)\b/.test(normalizedTranscript)) {
    return 'Posso abrir e fechar aplicativos, controlar janelas, pesquisar e ajustar o computador.';
  }

  if (/\b(obrigado|obrigada|valeu)\b/.test(normalizedTranscript)) {
    return 'Por nada! Estou à disposição.';
  }

  const safeTranscript = cleanTranscript.slice(0, MAX_TRANSCRIPT_LENGTH);

  return `Ouvi: ${safeTranscript}. Não consegui identificar uma ação segura. Pode dizer de outra forma?`;
}
