'use client';

import { useCallback, useEffect, useRef, useState } from 'react';

const API_BASE_URL = '/api';
const POLLING_INTERVAL_MS = 600;

export type BackgroundAssistantMode =
  | 'starting'
  | 'wake'
  | 'wake_detected'
  | 'command'
  | 'activated'
  | 'listening'
  | 'processing'
  | 'executing'
  | 'responding'
  | 'confirming'
  | 'completed'
  | 'speaking'
  | 'paused'
  | 'error';

export interface AssistantPermission {
  accepted: boolean;
  acceptedAt: string | null;
  level: 'total-user';
  termsVersion: number;
}

export interface AssistantAction {
  confidence: number;
  executed: boolean;
  id: string;
  name: string;
  risk: 'safe' | 'contextual' | 'confirmation_required' | 'blocked';
  status:
    | 'completed'
    | 'awaiting_confirmation'
    | 'confirmed'
    | 'cancelled'
    | 'expired'
    | 'error'
    | 'blocked'
    | 'permission_required';
}

export interface BackgroundAssistantState {
  connected: boolean;
  enabled: boolean;
  error: string;
  lastAction: AssistantAction | null;
  mode: BackgroundAssistantMode;
  partial: string;
  permission: AssistantPermission;
  response: string;
  sequence: number;
  transcript: string;
  wakePhrase: string;
  sttProvider?: string;
  voiceMetrics?: {
    activations: number;
    transcriptions: number;
    errors: number;
    fallbacks: number;
    audioSeconds: number;
    lastLatencyMs: number;
    lastProvider: string;
    estimatedCostUsd: number | null;
  };
}

interface BackgroundInteraction {
  response: string;
  transcript: string;
}

interface UseBackgroundAssistantOptions {
  onInteraction: (interaction: BackgroundInteraction) => void;
}

export function useBackgroundAssistant({
  onInteraction,
}: UseBackgroundAssistantOptions) {
  const [state, setState] = useState<BackgroundAssistantState | null>(null);
  const lastSequenceRef = useRef(-1);
  const onInteractionRef = useRef(onInteraction);

  useEffect(() => {
    onInteractionRef.current = onInteraction;
  }, [onInteraction]);

  useEffect(() => {
    let isActive = true;
    let timeoutId: ReturnType<typeof setTimeout> | undefined;

    async function poll() {
      try {
        const response = await fetch(`${API_BASE_URL}/state`, {
          cache: 'no-store',
          signal: AbortSignal.timeout(2_000),
        });

        if (!response.ok) {
          throw new Error('Background assistant unavailable');
        }

        const nextState = (await response.json()) as BackgroundAssistantState;
        if (!isActive) {
          return;
        }

        setState(nextState);

        if (
          nextState.sequence > lastSequenceRef.current &&
          (nextState.transcript || nextState.response)
        ) {
          lastSequenceRef.current = nextState.sequence;
          onInteractionRef.current({
            response: nextState.response,
            transcript: nextState.transcript,
          });
        }
      } catch {
        if (isActive) {
          setState(null);
        }
      } finally {
        if (isActive) {
          timeoutId = setTimeout(poll, POLLING_INTERVAL_MS);
        }
      }
    }

    void poll();

    return () => {
      isActive = false;
      if (timeoutId) {
        clearTimeout(timeoutId);
      }
    };
  }, []);

  const setListening = useCallback(async (enabled: boolean) => {
    const response = await fetch(`${API_BASE_URL}/listening`, {
      body: JSON.stringify({ enabled }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error('Não foi possível alterar a escuta contínua.');
    }

    const nextState = (await response.json()) as BackgroundAssistantState;
    setState(nextState);
  }, []);

  const setPermission = useCallback(async (accepted: boolean) => {
    const response = await fetch(`${API_BASE_URL}/permission`, {
      body: JSON.stringify({ accepted }),
      headers: { 'Content-Type': 'application/json' },
      method: 'POST',
    });

    if (!response.ok) {
      throw new Error('Não foi possível salvar a permissão de comandos.');
    }

    const nextState = (await response.json()) as BackgroundAssistantState;
    setState(nextState);
  }, []);

  return {
    isConnected: state !== null,
    setListening,
    setPermission,
    state,
  };
}
