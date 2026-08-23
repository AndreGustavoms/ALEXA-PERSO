import { VoiceAssistant } from '@/components/voice-assistant/VoiceAssistant';

export default function Home() {
  return (
    <main className="site-shell">
      <header className="site-header">
        <a className="brand" href="#assistant" aria-label="Assistente de voz - início">
          <span className="brand-mark" aria-hidden="true">
            <span />
            <span />
            <span />
          </span>
          <span className="brand-copy">
            <strong>Assistente de voz</strong>
            <small>Atendimento no navegador</small>
          </span>
        </a>

        <span className="version-label">Versão inicial</span>
      </header>

      <section className="assistant-section" id="assistant">
        <div className="section-heading">
          <p className="eyebrow">Conversa por voz</p>
          <h1>Como posso ajudar?</h1>
          <p>
            Toque no microfone, fale naturalmente e aguarde a resposta do
            assistente.
          </p>
        </div>

        <VoiceAssistant />
      </section>

      <footer className="site-footer">
        <span>O áudio é processado pelo recurso de fala do seu navegador.</span>
        <span>Use HTTPS ou localhost para acessar o microfone.</span>
      </footer>
    </main>
  );
}
