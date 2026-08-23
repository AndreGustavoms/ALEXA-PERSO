'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useClientReady } from '@/hooks/useClientReady';
import { getRecognitionErrorMessage } from '@/lib/speechErrors';
import type {
  BrowserSpeechRecognition,
  BrowserSpeechRecognitionErrorEvent,
  BrowserSpeechRecognitionEvent,
} from '@/types/speech-recognition';

type RecognitionAvailability =
  | { state: 'checking' }
  | { state: 'available' }
  | { state: 'unavailable'; reason: 'unsupported' | 'insecure-context' };

interface UseSpeechRecognitionOptions {
  language?: string;
  onResult: (transcript: string) => void;
  onError: (message: string) => void;
}

export function useSpeechRecognition({
  language = 'pt-BR',
  onResult,
  onError,
}: UseSpeechRecognitionOptions) {
  const recognitionRef = useRef<BrowserSpeechRecognition | null>(null);
  const onResultRef = useRef(onResult);
  const onErrorRef = useRef(onError);
  const [isListening, setIsListening] = useState(false);
  const isClientReady = useClientReady();

  const availability: RecognitionAvailability = !isClientReady
    ? { state: 'checking' }
    : !window.isSecureContext
      ? { state: 'unavailable', reason: 'insecure-context' }
      : window.SpeechRecognition ?? window.webkitSpeechRecognition
        ? { state: 'available' }
        : { state: 'unavailable', reason: 'unsupported' };

  useEffect(() => {
    onResultRef.current = onResult;
  }, [onResult]);

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    if (!window.isSecureContext) {
      return;
    }

    const Recognition =
      window.SpeechRecognition ?? window.webkitSpeechRecognition;

    if (!Recognition) {
      return;
    }

    const recognition = new Recognition();
    recognition.lang = language;
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onstart = () => {
      setIsListening(true);
    };

    recognition.onresult = (event: BrowserSpeechRecognitionEvent) => {
      const result = event.results.item(event.resultIndex);
      const transcript = result.item(0)?.transcript.trim() ?? '';

      setIsListening(false);

      if (transcript) {
        onResultRef.current(transcript);
      } else {
        onErrorRef.current('Não consegui identificar o que foi dito. Tente novamente.');
      }
    };

    recognition.onerror = (event: BrowserSpeechRecognitionErrorEvent) => {
      setIsListening(false);

      if (event.error !== 'aborted') {
        onErrorRef.current(getRecognitionErrorMessage(event.error));
      }
    };

    recognition.onend = () => {
      setIsListening(false);
    };

    recognitionRef.current = recognition;

    return () => {
      recognition.onstart = null;
      recognition.onresult = null;
      recognition.onerror = null;
      recognition.onend = null;
      recognition.abort();
      recognitionRef.current = null;
    };
  }, [language]);

  const start = useCallback(() => {
    if (!recognitionRef.current) {
      onErrorRef.current('O reconhecimento de voz não está disponível neste navegador.');
      return;
    }

    try {
      recognitionRef.current.start();
    } catch (caughtError) {
      if (!(caughtError instanceof DOMException && caughtError.name === 'InvalidStateError')) {
        onErrorRef.current('Não foi possível iniciar o microfone. Tente novamente.');
      }
    }
  }, []);

  const stop = useCallback(() => {
    if (!recognitionRef.current) {
      return;
    }

    try {
      recognitionRef.current.stop();
    } catch (caughtError) {
      if (!(caughtError instanceof DOMException && caughtError.name === 'InvalidStateError')) {
        onErrorRef.current('Não foi possível interromper o microfone corretamente.');
      }
    }

    setIsListening(false);
  }, []);

  return {
    availability,
    isListening,
    start,
    stop,
  };
}
