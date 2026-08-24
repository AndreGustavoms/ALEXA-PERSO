'use client';

import {
  AlertCircle,
  AudioLines,
  Mic,
  MicOff,
  RefreshCw,
  ShieldAlert,
  ShieldCheck,
  Settings,
  Square,
  Volume2,
  VolumeX,
} from 'lucide-react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { PermissionDialog } from './PermissionDialog';
import { SetupDialog } from './SetupDialog';
import { VoiceLabDialog } from './VoiceLabDialog';
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
  | 'finalizing'
  | 'transcribing'
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
    title: 'Ouvindo você...',
  },
  finalizing: {
    label: 'Finalizando',
    title: 'Finalizando áudio',
  },
  transcribing: {
    label: 'Entendendo',
    title: 'Entendendo...',
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
  const [isSetupOpen, setIsSetupOpen] = useState(false);
  const [isVoiceLabOpen, setIsVoiceLabOpen] = useState(false);
  const [devices, setDevices] = useState<Array<{ id: number; name: string; default: boolean }>>([]);
  const [microphoneDevice, setMicrophoneDevice] = useState<number | null>(null);
  const [updateChannel, setUpdateChannel] = useState<'stable' | 'beta' | 'dev'>('stable');
  const [autostart, setAutostartChoice] = useState(false);
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
    setAutostart,
    updateSettings,
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
  const onboardingComplete = backgroundState?.settings?.onboarding_complete;
  const configuredMicrophone = backgroundState?.settings?.microphone_device;
  const configuredChannel = backgroundState?.settings?.update_channel;
  const configuredAutostart = backgroundState?.autostart;

  useEffect(() => {
    if (
      isBackgroundConnected &&
      backgroundState?.permission &&
      onboardingComplete &&
      !backgroundState.permission.accepted &&
      !didPromptPermissionRef.current
    ) {
      didPromptPermissionRef.current = true;
      setIsPermissionOpen(true);
    }
  }, [backgroundState?.permission, isBackgroundConnected, onboardingComplete]);

  useEffect(() => {
    if (!isBackgroundConnected || configuredChannel === undefined) return;
    const timeout = window.setTimeout(() => {
      setMicrophoneDevice(configuredMicrophone ?? null);
      setUpdateChannel(configuredChannel);
      setAutostartChoice(Boolean(configuredAutostart));
      if (!onboardingComplete) setIsSetupOpen(true);
    }, 0);
    return () => window.clearTimeout(timeout);
  }, [configuredAutostart, configuredChannel, configuredMicrophone, isBackgroundConnected, onboardingComplete]);

  useEffect(() => {
    if (!isSetupOpen) return;
    void fetch('/api/audio/devices')
      .then((result) => result.json())
      .then((payload: { devices?: Array<{ id: number; name: string; default: boolean }> }) => setDevices(payload.devices || []))
      .catch(() => setDevices([]));
  }, [isSetupOpen]);

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
      : backgroundMode === 'activated' || backgroundMode === 'wake_detected'
        ? 'activated'
        : backgroundMode === 'command' ||
            backgroundMode === 'listening' ||
          isListening
        ? 'listening'
        : backgroundMode === 'finalizing'
          ? 'finalizing'
        : backgroundMode === 'transcribing'
          ? 'transcribing'
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
  const diagnostics = backgroundState?.voiceDiagnostics;
  const isSoundActive =
    isListening ||
    isSpeaking ||
    backgroundMode === 'command' ||
    backgroundMode === 'activated' ||
    backgroundMode === 'wake_detected' ||
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

  async function finishSetup() {
    setError('');
    try {
      await updateSettings({
        microphone_device: microphoneDevice,
        onboarding_complete: true,
        update_channel: updateChannel,
      });
      await setAutostart(autostart);
      setIsSetupOpen(false);
      if (!permissionAccepted) setIsPermissionOpen(true);
    } catch (caughtError) {
      setError(caughtError instanceof Error ? caughtError.message : 'Não foi possível concluir a configuração.');
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
                  className="icon-button"
                  type="button"
                  onClick={() => setIsVoiceLabOpen(true)}
                  aria-label="Voice Lab"
                  title="Voice Lab"
                >
                  <AudioLines aria-hidden="true" />
                </button>
              )}
              {isBackgroundConnected && (
                <button
                  className="icon-button"
                  type="button"
                  onClick={() => setIsSetupOpen(true)}
                  aria-label="Configurações"
                  title="Configurações"
                >
                  <Settings aria-hidden="true" />
                </button>
              )}
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
            <div className="empty-conversation">
              <img src="/doktor-mark.svg" alt="" />
              <p className="empty-conversation__title">Nenhuma atividade ainda</p>
              <p className="empty-conversation__hint">
                Diga <strong>&ldquo;Olá, Doktor&rdquo;</strong> e aguarde o sinal sonoro para
                falar. O que você pedir e a resposta aparecem aqui.
              </p>
              {!isBackgroundConnected && (
                <p className="empty-conversation__offline">
                  O assistente em segundo plano não está em execução — inicie o Doktor
                  Assistant para usar a voz.
                </p>
              )}
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
        <PermissionDialog
          permissionAccepted={permissionAccepted}
          hasConfirmedPermission={hasConfirmedPermission}
          onConfirmChange={setHasConfirmedPermission}
          onPermissionChange={(aceitar) => void handlePermissionChange(aceitar)}
          onClose={closePermissionDialog}
        />
      )}

      {isSetupOpen && (
        <SetupDialog
          backgroundState={backgroundState}
          devices={devices}
          microphoneDevice={microphoneDevice}
          onMicrophoneChange={setMicrophoneDevice}
          updateChannel={updateChannel}
          onUpdateChannelChange={setUpdateChannel}
          autostart={autostart}
          onAutostartChange={setAutostartChoice}
          onFinish={() => void finishSetup()}
          onClose={() => setIsSetupOpen(false)}
        />
      )}

      {isVoiceLabOpen && diagnostics && (
        <VoiceLabDialog
          diagnostics={diagnostics}
          commandDebug={backgroundState?.commandDebug}
          onClose={() => setIsVoiceLabOpen(false)}
        />
      )}
    </>
  );
}
