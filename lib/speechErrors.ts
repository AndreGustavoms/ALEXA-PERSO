import type { SpeechRecognitionErrorCode } from '@/types/speech-recognition';

const recognitionErrorMessages: Record<SpeechRecognitionErrorCode, string> = {
  aborted: 'A escuta foi interrompida.',
  'audio-capture': 'Nenhum microfone foi encontrado. Verifique o dispositivo de áudio.',
  'bad-grammar': 'O navegador não conseguiu interpretar a configuração de fala.',
  language: 'O idioma selecionado não está disponível para reconhecimento.',
  network: 'O serviço de reconhecimento está sem conexão. Verifique sua internet.',
  'no-speech': 'Nenhuma fala foi detectada. Aproxime-se do microfone e tente novamente.',
  'not-allowed': 'O acesso ao microfone foi bloqueado. Libere a permissão nas configurações do navegador.',
  'phrases-not-supported': 'Este navegador não aceita a configuração de reconhecimento usada.',
  'service-not-allowed': 'O serviço de reconhecimento de voz foi bloqueado pelo navegador.',
};

export function getRecognitionErrorMessage(error: SpeechRecognitionErrorCode) {
  return (
    recognitionErrorMessages[error] ??
    'Ocorreu um problema ao reconhecer sua fala. Tente novamente.'
  );
}
