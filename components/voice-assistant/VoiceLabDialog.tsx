'use client';

import { AudioLines } from 'lucide-react';
import { Dialog } from './Dialog';
import type { BackgroundAssistantState } from '@/hooks/useBackgroundAssistant';

type Diagnostics = NonNullable<BackgroundAssistantState['voiceDiagnostics']>;

export type VoiceLabDialogProps = {
  diagnostics: Diagnostics;
  commandDebug?: BackgroundAssistantState['commandDebug'];
  onClose: () => void;
};

const dbfs = (valor: number | undefined) => (valor ? 20 * Math.log10(valor) : -96);

/* A barra cobre de -72 dBFS (silêncio útil) a 0 dBFS (saturação). */
const larguraDoSinal = (valor: number) =>
  `${Math.max(0, Math.min(100, ((valor + 72) / 72) * 100))}%`;

export function VoiceLabDialog({ diagnostics, commandDebug, onClose }: VoiceLabDialogProps) {
  const bruto = dbfs(diagnostics.rawRms);
  const processado = dbfs(diagnostics.processedRms);
  const ruido = dbfs(diagnostics.noiseFloor);

  return (
    <Dialog
      id="voice-lab"
      className="voice-lab-dialog"
      kicker="Diagnóstico local"
      titulo="Doktor Voice Lab"
      icone={<AudioLines />}
      aoFechar={onClose}
    >
      <div className="permission-content voice-lab-content">
        <div className="voice-lab-signal">
          <span>Entrada bruta</span>
          <strong>{bruto.toFixed(1)} dBFS</strong>
          <div><i style={{ width: larguraDoSinal(bruto) }} /></div>
        </div>
        <div className="voice-lab-signal">
          <span>Processado</span>
          <strong>{processado.toFixed(1)} dBFS</strong>
          <div><i style={{ width: larguraDoSinal(processado) }} /></div>
        </div>

        <dl className="voice-lab-metrics">
          <div><dt>Noise floor</dt><dd>{ruido.toFixed(1)} dBFS</dd></div>
          <div><dt>Silero</dt><dd>{(diagnostics.vadProbability * 100).toFixed(0)}%</dd></div>
          <div><dt>Wake score</dt><dd>{diagnostics.wakeScore === null ? 'N/D' : diagnostics.wakeScore.toFixed(2)}</dd></div>
          <div><dt>Threshold</dt><dd>{diagnostics.wakeThreshold === null ? 'N/D' : diagnostics.wakeThreshold.toFixed(2)}</dd></div>
          <div><dt>Estado</dt><dd>{diagnostics.vadState}</dd></div>
          <div><dt>Silêncio</dt><dd>{diagnostics.silenceDurationMs} ms</dd></div>
          <div><dt>Buffer</dt><dd>{diagnostics.bufferDurationMs} ms</dd></div>
          <div><dt>Ganho</dt><dd>{diagnostics.gain.toFixed(1)}x</dd></div>
        </dl>

        <div className="voice-lab-engines">
          <span>Wake</span><strong>{diagnostics.wakeEngine}</strong>
          <span>VAD</span><strong>{diagnostics.vadEngine}</strong>
        </div>

        {commandDebug && (
          <dl className="command-debug">
            <div><dt>Ouvido</dt><dd>{commandDebug.heard}</dd></div>
            <div><dt>Normalizado</dt><dd>{commandDebug.normalized}</dd></div>
            <div><dt>Intenção</dt><dd>{commandDebug.intent}</dd></div>
            <div><dt>Entidade</dt><dd>{commandDebug.entity || 'N/D'}</dd></div>
            <div><dt>Confiança</dt><dd>{Math.round(commandDebug.confidence * 100)}%</dd></div>
            <div><dt>Origem</dt><dd>{commandDebug.source}</dd></div>
            <div><dt>Alvo</dt><dd>{commandDebug.resolvedTarget || 'N/D'}</dd></div>
            <div><dt>Rota</dt><dd>{commandDebug.route || 'N/D'}</dd></div>
            <div><dt>Execução</dt><dd>{commandDebug.execution}</dd></div>
          </dl>
        )}
      </div>
    </Dialog>
  );
}
