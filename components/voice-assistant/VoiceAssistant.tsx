'use client';

import {
  AlertCircle,
  Mic,
  RefreshCw,
  Square,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { useCallback, useMemo, useState } from 'react';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import { useSpeechSynthesis } from '@/hooks/useSpeechSynthesis';
import { createAssistantReply } from '@/lib/createAssistantReply';

type AssistantStatus = 'idle' | 'listening' | 'speaking' | 'error';

const statusContent: Record<
  AssistantStatus,
  { label: string; title: string; description: string }
> = {
  idle: {
    label: 'Pronto para começar',
    title: 'Toque para falar',
    description: 'O navegador pedirá acesso ao microfone na primeira vez.',
  },
  listening: {
    label: 'Microfone ativo',
    title: 'Estou ouvindo',
    description: 'Fale agora. A escuta termina automaticamente quando você parar.',
  },
  speaking: {
    label: 'Respondendo',
    title: 'Falando com você',
    description: 'Toque no botão para interromper a resposta.',
  },
  error: {
    label: 'Atenção necessária',
    title: 'Não consegui ouvir',
    description: 'Confira a mensagem ao lado e tente novamente.',
  },
};

export function VoiceAssistant() {
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [error, setError] = useState('');

  const handleSynthesisError = useCallback((message: string) => {
    setError(message);
  }, []);

  const {
    availability: synthesisAvailability,
    cancel: cancelSpeech,
    isSpeaking,
    speak,
  } = useSpeechSynthesis({
    language: 'pt-BR',
    onError: handleSynthesisError,
  });

  const handleTranscript = useCallback(
    (recognizedText: string) => {
      const reply = createAssistantReply(recognizedText);

      setError('');
      setTranscript(recognizedText);
      setResponse(reply);
      speak(reply);
    },
    [speak],
  );

  const handleRecognitionError = useCallback((message: string) => {
    setError(message);
  }, []);

  const {
    availability: recognitionAvailability,
    isListening,
    start: startListening,
    stop: stopListening,
  } = useSpeechRecognition({
    language: 'pt-BR',
    onError: handleRecognitionError,
    onResult: handleTranscript,
  });

  const status: AssistantStatus = error
    ? 'error'
    : isListening
      ? 'listening'
      : isSpeaking
        ? 'speaking'
        : 'idle';

  const content = statusContent[status];
  const isCheckingSupport =
    recognitionAvailability.state === 'checking' ||
    synthesisAvailability === 'checking';
  const recognitionUnavailable = recognitionAvailability.state === 'unavailable';
  const synthesisUnavailable = synthesisAvailability === 'unavailable';
  const canStart = !isCheckingSupport && !recognitionUnavailable;

  const supportMessage = useMemo(() => {
    if (recognitionAvailability.state !== 'unavailable') {
      return '';
    }

    if (recognitionAvailability.reason === 'insecure-context') {
      return 'O microfone só pode ser usado em uma conexão HTTPS ou em localhost.';
    }

    return 'O reconhecimento de voz não está disponível neste navegador. Tente usar uma versão atual do Chrome ou Edge.';
  }, [recognitionAvailability]);

  function handleMainAction() {
    setError('');

    if (isListening) {
      stopListening();
      return;
    }

    if (isSpeaking) {
      cancelSpeech();
      return;
    }

    cancelSpeech();
    startListening();
  }

  function handleReset() {
    stopListening();
    cancelSpeech();
    setTranscript('');
    setResponse('');
    setError('');
  }

  const buttonLabel = isListening
    ? 'Parar de ouvir'
    : isSpeaking
      ? 'Interromper resposta'
      : 'Iniciar conversa por voz';

  return (
    <div className="assistant-workspace">
      <section className={`voice-stage voice-stage--${status}`}>
        <div className="status-line" role="status" aria-live="polite">
          <span className="status-dot" aria-hidden="true" />
          {isCheckingSupport ? 'Verificando o navegador' : content.label}
        </div>

        <div className="voice-control">
          <span className="pulse-ring pulse-ring--outer" aria-hidden="true" />
          <span className="pulse-ring pulse-ring--inner" aria-hidden="true" />
          <button
            className="voice-button"
            type="button"
            onClick={handleMainAction}
            disabled={!canStart && !isSpeaking}
            aria-label={buttonLabel}
            title={buttonLabel}
          >
            {isListening || isSpeaking ? (
              <Square aria-hidden="true" strokeWidth={2.25} />
            ) : (
              <Mic aria-hidden="true" strokeWidth={2.25} />
            )}
          </button>
        </div>

        <div className="voice-copy">
          <h2>{isCheckingSupport ? 'Só um instante' : content.title}</h2>
          <p>
            {isCheckingSupport
              ? 'Estamos conferindo os recursos de voz disponíveis.'
              : content.description}
          </p>
        </div>

        <div
          className={`sound-meter ${isListening || isSpeaking ? 'is-active' : ''}`}
          aria-hidden="true"
        >
          <span />
          <span />
          <span />
          <span />
          <span />
        </div>
      </section>

      <section className="conversation-panel" aria-labelledby="conversation-title">
        <div className="conversation-header">
          <div>
            <p className="panel-kicker">Última interação</p>
            <h2 id="conversation-title">Conversa</h2>
          </div>

          {(transcript || response || error) && (
            <button
              className="icon-button"
              type="button"
              onClick={handleReset}
              aria-label="Limpar conversa"
              title="Limpar conversa"
            >
              <RefreshCw aria-hidden="true" />
            </button>
          )}
        </div>

        <div className="conversation-content" aria-live="polite" aria-atomic="false">
          {supportMessage ? (
            <div className="notice notice--warning" role="alert">
              <AlertCircle aria-hidden="true" />
              <div>
                <strong>Recurso indisponível</strong>
                <p>{supportMessage}</p>
              </div>
            </div>
          ) : error ? (
            <div className="notice notice--error" role="alert">
              <AlertCircle aria-hidden="true" />
              <div>
                <strong>Não foi possível continuar</strong>
                <p>{error}</p>
              </div>
            </div>
          ) : !transcript && !response ? (
            <div className="empty-conversation">
              <span className="empty-icon" aria-hidden="true">
                <Volume2 />
              </span>
              <h3>Sua conversa aparecerá aqui</h3>
              <p>Experimente dizer “Olá” ou perguntar o que o assistente faz.</p>
            </div>
          ) : (
            <div className="message-list">
              {transcript && (
                <article className="message message--visitor">
                  <span>Você</span>
                  <p>{transcript}</p>
                </article>
              )}

              {response && (
                <article className="message message--assistant">
                  <span>Assistente</span>
                  <p>{response}</p>
                  {!synthesisUnavailable && (
                    <button
                      className="replay-button"
                      type="button"
                      onClick={() => (isSpeaking ? cancelSpeech() : speak(response))}
                    >
                      {isSpeaking ? (
                        <VolumeX aria-hidden="true" />
                      ) : (
                        <Volume2 aria-hidden="true" />
                      )}
                      {isSpeaking ? 'Interromper' : 'Ouvir novamente'}
                    </button>
                  )}
                </article>
              )}
            </div>
          )}
        </div>

        <div className="compatibility-note">
          <span aria-hidden="true" />
          {synthesisUnavailable
            ? 'A resposta será exibida em texto porque a voz não está disponível.'
            : 'Resposta em português do Brasil'}
        </div>
      </section>
    </div>
  );
}
