'use client';

import { Mic } from 'lucide-react';
import { Dialog } from './Dialog';
import type { BackgroundAssistantState } from '@/hooks/useBackgroundAssistant';

export type AudioDevice = { id: number; name: string; default: boolean };

export type SetupDialogProps = {
  backgroundState: BackgroundAssistantState | null;
  devices: AudioDevice[];
  microphoneDevice: number | null;
  onMicrophoneChange: (id: number | null) => void;
  updateChannel: 'stable' | 'beta' | 'dev';
  onUpdateChannelChange: (canal: 'stable' | 'beta' | 'dev') => void;
  autostart: boolean;
  onAutostartChange: (ativo: boolean) => void;
  onFinish: () => void;
  onClose: () => void;
};

export function SetupDialog({
  backgroundState,
  devices,
  microphoneDevice,
  onMicrophoneChange,
  updateChannel,
  onUpdateChannelChange,
  autostart,
  onAutostartChange,
  onFinish,
  onClose,
}: SetupDialogProps) {
  const diagnostics = backgroundState?.voiceDiagnostics;
  // Durante o onboarding o diálogo não oferece X, Escape nem backdrop: a saída é
  // o botão "Concluir" do rodapé, que grava as escolhas. Depois de concluído uma
  // vez, passa a fechar como qualquer outro.
  const concluido = Boolean(backgroundState?.settings?.onboarding_complete);

  return (
    <Dialog
      id="setup"
      className="setup-dialog"
      kicker={`Doktor ${backgroundState?.version ?? ''}`.trim()}
      titulo="Configurar assistente"
      icone={<Mic />}
      aoFechar={concluido ? onClose : undefined}
      rodape={
        <footer className="permission-footer">
          <button className="primary-button" type="button" onClick={onFinish}>
            Concluir
          </button>
        </footer>
      }
    >
      <div className="permission-content setup-fields">
        <label>
          <span>Microfone</span>
          <select
            value={microphoneDevice ?? ''}
            onChange={(event) =>
              onMicrophoneChange(event.target.value === '' ? null : Number(event.target.value))
            }
          >
            <option value="">Padrão do sistema</option>
            {devices.map((device) => (
              <option key={device.id} value={device.id}>
                {device.name}
                {device.default ? ' (padrão)' : ''}
              </option>
            ))}
          </select>
        </label>

        <div className="level-field">
          <span>Nível de entrada</span>
          <div className="input-level">
            <i style={{ width: `${Math.min(100, (backgroundState?.audioLevel ?? 0) * 180)}%` }} />
          </div>
        </div>

        {diagnostics && (
          <dl className="voice-diagnostics">
            <div><dt>RAW RMS</dt><dd>{diagnostics.rawRms.toFixed(4)}</dd></div>
            <div><dt>Processado</dt><dd>{diagnostics.processedRms.toFixed(4)}</dd></div>
            <div><dt>Ruído</dt><dd>{diagnostics.noiseFloor.toFixed(4)}</dd></div>
            <div><dt>Ganho</dt><dd>{diagnostics.gain.toFixed(1)}x</dd></div>
            <div><dt>VAD</dt><dd>{diagnostics.vadState}</dd></div>
            <div><dt>Silêncio</dt><dd>{diagnostics.silenceDurationMs} ms</dd></div>
          </dl>
        )}

        <label>
          <span>Atualizações</span>
          <select
            value={updateChannel}
            onChange={(event) =>
              onUpdateChannelChange(event.target.value as 'stable' | 'beta' | 'dev')
            }
          >
            <option value="stable">Estável</option>
            <option value="beta">Beta</option>
            <option value="dev">Desenvolvimento</option>
          </select>
        </label>

        <label className="setup-toggle">
          <input
            type="checkbox"
            checked={autostart}
            onChange={(event) => onAutostartChange(event.target.checked)}
          />
          <span>Iniciar com o sistema</span>
        </label>
      </div>
    </Dialog>
  );
}
