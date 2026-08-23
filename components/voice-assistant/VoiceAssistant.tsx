'use client';

import {
  AlertCircle,
  Mic,
  MicOff,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Square,
  Volume2,
  VolumeX,
  X,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useBackgroundAssistant } from '@/hooks/useBackgroundAssistant';
import { useSpeechRecognition } from '@/hooks/useSpeechRecognition';
import { useSpeechSynthesis } from '@/hooks/useSpeechSynthesis';
import { createAssistantReply } from '@/lib/createAssistantReply';

type AssistantStatus =
  | 'idle'
  | 'background'
  | 'paused'
  | 'activated'
  | 'listening'
  | 'processing'
  | 'executing'
  | 'confirming'
  | 'speaking'
  | 'error';

const statusContent: Record<
  AssistantStatus,
  { label: string; title: string }
> = {
  idle: {
    label: 'Manual',
    title: 'Toque para falar',
  },
  background: {
    label: 'Ativo',
    title: 'Olá, Doktor',
  },
  paused: {
    label: 'Pausado',
    title: 'Escuta pausada',
  },
  activated: {
    label: 'Ativado',
    title: 'Pode falar',
  },
  listening: {
    label: 'Ouvindo',
    title: 'Estou ouvindo',
  },
  processing: {
    label: 'Processando',
    title: 'Entendendo',
  },
  executing: {
    label: 'Executando',
    title: 'Em andamento',
  },
  confirming: {
    label: 'Confirmação',
    title: 'Sim ou não?',
  },
  speaking: {
    label: 'Respondendo',
    title: 'Respondendo',
  },
  error: {
    label: 'Erro',
    title: 'Tente novamente',
  },
};

export function VoiceAssistant() {
  const [transcript, setTranscript] = useState('');
  const [response, setResponse] = useState('');
  const [error, setError] = useState('');
  const [isPermissionOpen, setIsPermissionOpen] = useState(false);
  const [hasConfirmedPermission, setHasConfirmedPermission] = useState(false);
  const didPromptPermissionRef = useRef(false);

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

  const handleBackgroundInteraction = useCallback(
    (interaction: { response: string; transcript: string }) => {
      cancelSpeech();
      setError('');
      setTranscript(interaction.transcript);
      setResponse(interaction.response);
    },
    [cancelSpeech],
  );

  const {
    isConnected: isBackgroundConnected,
    setListening: setBackgroundListening,
    setPermission,
    state: backgroundState,
  } = useBackgroundAssistant({
    onInteraction: handleBackgroundInteraction,
  });

  const handleTranscript = useCallback(
    (recognizedText: string) => {
      const reply = createAssistantReply(recognizedText);

      setError('');
      setTranscript(recognizedText);
      setResponse(reply);

      if (synthesisAvailability === 'available') {
        speak(reply);
      }
    },
    [speak, synthesisAvailability],
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

  const backgroundError =
    backgroundState?.mode === 'error' ? backgroundState.error : '';
  const displayError = error || backgroundError;
  const isCheckingSupport =
    !isBackgroundConnected &&
    (recognitionAvailability.state === 'checking' ||
      synthesisAvailability === 'checking');
  const recognitionUnavailable =
    !isBackgroundConnected && recognitionAvailability.state === 'unavailable';
  const synthesisUnavailable =
    !isBackgroundConnected && synthesisAvailability === 'unavailable';
  const canStart =
    isBackgroundConnected || (!isCheckingSupport && !recognitionUnavailable);
  const backgroundMode = backgroundState?.mode;
  const backgroundEnabled = backgroundState?.enabled ?? false;
  const permissionAccepted = backgroundState?.permission.accepted ?? false;

  useEffect(() => {
    if (
      isBackgroundConnected &&
      backgroundState?.permission &&
      !backgroundState.permission.accepted &&
      !didPromptPermissionRef.current
    ) {
      didPromptPermissionRef.current = true;
      setIsPermissionOpen(true);
    }
  }, [backgroundState?.permission, isBackgroundConnected]);

  useEffect(() => {
    if (!isPermissionOpen) {
      return;
    }

    function handleEscape(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        setIsPermissionOpen(false);
        setHasConfirmedPermission(false);
      }
    }

    window.addEventListener('keydown', handleEscape);
    return () => window.removeEventListener('keydown', handleEscape);
  }, [isPermissionOpen]);

  const status: AssistantStatus = displayError || recognitionUnavailable
    ? 'error'
    : isBackgroundConnected && !backgroundEnabled
      ? 'paused'
      : backgroundMode === 'activated'
        ? 'activated'
        : backgroundMode === 'command' ||
            backgroundMode === 'listening' ||
          isListening
        ? 'listening'
        : backgroundMode === 'processing'
          ? 'processing'
          : backgroundMode === 'executing'
            ? 'executing'
          : backgroundMode === 'confirming'
            ? 'confirming'
        : backgroundMode === 'speaking' || backgroundMode === 'responding' || isSpeaking
          ? 'speaking'
          : isBackgroundConnected
            ? 'background'
            : 'idle';

  const content = statusContent[status];
  const isSoundActive =
    isListening ||
    isSpeaking ||
    backgroundMode === 'command' ||
    backgroundMode === 'activated' ||
    backgroundMode === 'listening' ||
    backgroundMode === 'speaking' ||
    backgroundMode === 'responding' ||
    backgroundMode === 'processing' ||
    backgroundMode === 'executing';

  const supportMessage = useMemo(() => {
    if (
      isBackgroundConnected ||
      recognitionAvailability.state !== 'unavailable'
    ) {
      return '';
    }

    if (recognitionAvailability.reason === 'insecure-context') {
      return 'O microfone só pode ser usado em uma conexão HTTPS ou em localhost.';
    }

    return 'O reconhecimento de voz não está disponível neste navegador. Inicie o aplicativo local ou tente uma versão atual do Chrome ou Edge.';
  }, [isBackgroundConnected, recognitionAvailability]);

  async function handleMainAction() {
    setError('');

    if (isBackgroundConnected) {
      try {
        await setBackgroundListening(!backgroundEnabled);
      } catch (caughtError) {
        setError(
          caughtError instanceof Error
            ? caughtError.message
            : 'Não foi possível alterar a escuta contínua.',
        );
      }
      return;
    }

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

  function closePermissionDialog() {
    setIsPermissionOpen(false);
    setHasConfirmedPermission(false);
  }

  async function handlePermissionChange(accepted: boolean) {
    setError('');
    try {
      await setPermission(accepted);
      closePermissionDialog();
    } catch (caughtError) {
      setError(
        caughtError instanceof Error
          ? caughtError.message
          : 'Não foi possível alterar a permissão de comandos.',
      );
    }
  }

  const buttonLabel = isBackgroundConnected
    ? backgroundEnabled
      ? 'Pausar escuta contínua'
      : 'Ativar escuta contínua'
    : isListening
      ? 'Parar de ouvir'
      : isSpeaking
        ? 'Interromper resposta'
        : 'Iniciar conversa por voz';

  return (
    <>
      <div className="assistant-workspace">
        <section className={`voice-stage voice-stage--${status}`}>
        <div className="status-line" role="status" aria-live="polite">
          <span className="status-dot" aria-hidden="true" />
          {isCheckingSupport ? 'Verificando o navegador' : content.label}
        </div>
        <img className="stage-mark" src="/doktor-mark.svg" alt="" />

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
            {isBackgroundConnected ? (
              backgroundEnabled ? (
                <Mic aria-hidden="true" strokeWidth={2.25} />
              ) : (
                <MicOff aria-hidden="true" strokeWidth={2.25} />
              )
            ) : isListening || isSpeaking ? (
              <Square aria-hidden="true" strokeWidth={2.25} />
            ) : (
              <Mic aria-hidden="true" strokeWidth={2.25} />
            )}
          </button>
        </div>

        <div className="voice-copy">
          <h2>{isCheckingSupport ? 'Iniciando' : content.title}</h2>
        </div>

        <div
          className={`sound-meter ${isSoundActive ? 'is-active' : ''}`}
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
            <h2 id="conversation-title">Atividade</h2>

            <div className="conversation-actions">
              {isBackgroundConnected && (
                <button
                  className={`icon-button permission-button ${permissionAccepted ? 'is-active' : ''}`}
                  type="button"
                  onClick={() => setIsPermissionOpen(true)}
                  aria-label={permissionAccepted ? 'Comandos autorizados' : 'Autorizar comandos'}
                  title={permissionAccepted ? 'Comandos autorizados' : 'Autorizar comandos'}
                >
                  {permissionAccepted ? (
                    <ShieldCheck aria-hidden="true" />
                  ) : (
                    <ShieldAlert aria-hidden="true" />
                  )}
                </button>
              )}

              {(transcript || response || displayError) && (
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
          ) : displayError ? (
            <div className="notice notice--error" role="alert">
              <AlertCircle aria-hidden="true" />
              <div>
                <strong>Não foi possível continuar</strong>
                <p>{displayError}</p>
              </div>
            </div>
          ) : !transcript && !response ? (
            <div className="empty-conversation" aria-label="Nenhuma atividade recente">
              <img src="/doktor-mark.svg" alt="" />
            </div>
          ) : (
            <div className="message-list">
              {transcript && (
                <article className="message message--visitor">
                  <span>Você</span>
                  <p>{transcript}</p>
                </article>
              )}

              {backgroundState?.lastAction?.name && (
                <div
                  className={`intent-summary intent-summary--${backgroundState.lastAction.status}`}
                  role="status"
                >
                  <span>Intenção</span>
                  <strong>{backgroundState.lastAction.name}</strong>
                  {backgroundState.lastAction.status === 'awaiting_confirmation' && (
                    <em>Aguardando confirmação</em>
                  )}
                </div>
              )}

              {response && (
                <article className="message message--assistant">
                  <span>Doktor</span>
                  <p>{response}</p>
                  {!synthesisUnavailable && (
                    <button
                      className="replay-button"
                      type="button"
                      onClick={() => (isSpeaking ? cancelSpeech() : speak(response))}
                      aria-label={isSpeaking ? 'Interromper resposta' : 'Ouvir novamente'}
                      title={isSpeaking ? 'Interromper resposta' : 'Ouvir novamente'}
                    >
                      {isSpeaking ? (
                        <VolumeX aria-hidden="true" />
                      ) : (
                        <Volume2 aria-hidden="true" />
                      )}
                    </button>
                  )}
                </article>
              )}
            </div>
          )}
          </div>
        </section>
      </div>

      {isPermissionOpen && (
        <div
          className="permission-backdrop"
          role="presentation"
          onMouseDown={(event) => {
            if (event.target === event.currentTarget) {
              closePermissionDialog();
            }
          }}
        >
          <section
            className="permission-dialog"
            role="dialog"
            aria-modal="true"
            aria-labelledby="permission-title"
          >
            <header className="permission-header">
              <span className="permission-icon" aria-hidden="true">
                {permissionAccepted ? <ShieldCheck /> : <ShieldAlert />}
              </span>
              <div>
                <p className="panel-kicker">Autorização local</p>
                <h2 id="permission-title">Permissão total para ações locais</h2>
              </div>
              <button
                className="icon-button"
                type="button"
                onClick={closePermissionDialog}
                aria-label="Fechar autorização"
                title="Fechar"
              >
                <X aria-hidden="true" />
              </button>
            </header>

            <div className="permission-content">
              <p>
                Esta autorização permite que a Doktor Assistant execute comandos de voz
                registrados usando os privilégios da sua conta atual do Windows.
              </p>
              <ul>
                <li>Abrir aplicativos, sites, pesquisas e pastas.</li>
                <li>Controlar volume, reprodução e outras ações implementadas.</li>
                <li>Continuar ativo em segundo plano aguardando a frase de ativação.</li>
              </ul>
              <div className="permission-warning">
                <ShieldAlert aria-hidden="true" />
                <p>
                  Uma pessoa ou áudio próximo ao microfone também pode dar comandos.
                  Esta permissão não ignora o UAC, e ações destrutivas continuam
                  exigindo confirmação forte.
                </p>
              </div>

              {permissionAccepted ? (
                <p className="permission-status">
                  <ShieldCheck aria-hidden="true" />
                  Permissão ativa neste computador.
                </p>
              ) : (
                <label className="permission-consent">
                  <input
                    type="checkbox"
                    checked={hasConfirmedPermission}
                    onChange={(event) =>
                      setHasConfirmedPermission(event.target.checked)
                    }
                    autoFocus
                  />
                  <span>
                    Li e autorizo a Doktor Assistant a executar essas ações quando forem
                    solicitadas por voz.
                  </span>
                </label>
              )}
            </div>

            <footer className="permission-footer">
              <button
                className="secondary-button"
                type="button"
                onClick={closePermissionDialog}
              >
                Fechar
              </button>
              {permissionAccepted ? (
                <button
                  className="danger-button"
                  type="button"
                  onClick={() => void handlePermissionChange(false)}
                >
                  Revogar permissão
                </button>
              ) : (
                <button
                  className="primary-button"
                  type="button"
                  disabled={!hasConfirmedPermission}
                  onClick={() => void handlePermissionChange(true)}
                >
                  <ShieldCheck aria-hidden="true" />
                  Aceitar e ativar
                </button>
              )}
            </footer>
          </section>
        </div>
      )}
    </>
  );
}
