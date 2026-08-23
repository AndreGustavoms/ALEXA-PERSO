'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { useClientReady } from '@/hooks/useClientReady';

type SynthesisAvailability = 'checking' | 'available' | 'unavailable';

interface UseSpeechSynthesisOptions {
  language?: string;
  onError: (message: string) => void;
}

export function useSpeechSynthesis({
  language = 'pt-BR',
  onError,
}: UseSpeechSynthesisOptions) {
  const utteranceRef = useRef<SpeechSynthesisUtterance | null>(null);
  const onErrorRef = useRef(onError);
  const [isSpeaking, setIsSpeaking] = useState(false);
  const isClientReady = useClientReady();
  const availability: SynthesisAvailability = !isClientReady
    ? 'checking'
    : 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window
      ? 'available'
      : 'unavailable';

  useEffect(() => {
    onErrorRef.current = onError;
  }, [onError]);

  useEffect(() => {
    if (!('speechSynthesis' in window) || !('SpeechSynthesisUtterance' in window)) {
      return;
    }

    return () => {
      window.speechSynthesis.cancel();
      utteranceRef.current = null;
    };
  }, []);

  const cancel = useCallback(() => {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }

    utteranceRef.current = null;
    setIsSpeaking(false);
  }, []);

  const speak = useCallback(
    (text: string) => {
      if (
        !text ||
        !('speechSynthesis' in window) ||
        !('SpeechSynthesisUtterance' in window)
      ) {
        onErrorRef.current(
          'A resposta foi gerada, mas este navegador não consegue reproduzir voz.',
        );
        return;
      }

      window.speechSynthesis.cancel();

      const utterance = new SpeechSynthesisUtterance(text);
      const voices = window.speechSynthesis.getVoices();
      const normalizedLanguage = language.toLowerCase();
      const preferredVoice =
        voices.find((voice) => voice.lang.toLowerCase() === normalizedLanguage) ??
        voices.find((voice) =>
          voice.lang.toLowerCase().startsWith(normalizedLanguage.split('-')[0]),
        );

      utterance.lang = language;
      utterance.rate = 1;
      utterance.pitch = 1;

      if (preferredVoice) {
        utterance.voice = preferredVoice;
      }

      utterance.onstart = () => {
        if (utteranceRef.current === utterance) {
          setIsSpeaking(true);
        }
      };

      utterance.onend = () => {
        if (utteranceRef.current === utterance) {
          utteranceRef.current = null;
          setIsSpeaking(false);
        }
      };

      utterance.onerror = (event) => {
        if (utteranceRef.current !== utterance) {
          return;
        }

        utteranceRef.current = null;
        setIsSpeaking(false);

        if (event.error !== 'canceled' && event.error !== 'interrupted') {
          onErrorRef.current('Não foi possível reproduzir a resposta em voz alta.');
        }
      };

      utteranceRef.current = utterance;
      setIsSpeaking(true);
      window.speechSynthesis.speak(utterance);
    },
    [language],
  );

  return {
    availability,
    cancel,
    isSpeaking,
    speak,
  };
}
