import { VoiceAssistant } from '@/components/voice-assistant/VoiceAssistant';

export function App() {
  return (
    <main className="site-shell">
      <header className="site-header">
        <a className="brand" href="#assistant" aria-label="Doktor Assistant - início">
          <img className="brand-mark" src="/doktor-mark.svg" alt="" />
          <span className="brand-copy">
            <h1>Doktor Assistant</h1>
            <small>Voice system</small>
          </span>
        </a>

        <span className="version-label">
          <span aria-hidden="true" />
          Local
        </span>
      </header>

      <section className="assistant-section" id="assistant">
        <VoiceAssistant />
      </section>
    </main>
  );
}
