'use client';

import { ShieldAlert, ShieldCheck } from 'lucide-react';
import { Dialog } from './Dialog';

export type PermissionDialogProps = {
  permissionAccepted: boolean;
  hasConfirmedPermission: boolean;
  onConfirmChange: (confirmado: boolean) => void;
  onPermissionChange: (aceitar: boolean) => void;
  onClose: () => void;
};

export function PermissionDialog({
  permissionAccepted,
  hasConfirmedPermission,
  onConfirmChange,
  onPermissionChange,
  onClose,
}: PermissionDialogProps) {
  return (
    <Dialog
      id="permission"
      kicker="Autorização local"
      titulo="Permissão total para ações locais"
      icone={permissionAccepted ? <ShieldCheck /> : <ShieldAlert />}
      aoFechar={onClose}
      rodape={
        <footer className="permission-footer">
          <button className="secondary-button" type="button" onClick={onClose}>
            Fechar
          </button>
          {permissionAccepted ? (
            <button
              className="danger-button"
              type="button"
              onClick={() => onPermissionChange(false)}
            >
              Revogar permissão
            </button>
          ) : (
            <button
              className="primary-button"
              type="button"
              disabled={!hasConfirmedPermission}
              onClick={() => onPermissionChange(true)}
            >
              <ShieldCheck aria-hidden="true" />
              Aceitar e ativar
            </button>
          )}
        </footer>
      }
    >
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
            Uma pessoa ou áudio próximo ao microfone também pode dar comandos. Esta
            permissão não ignora o UAC, e ações destrutivas continuam exigindo
            confirmação forte.
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
              onChange={(event) => onConfirmChange(event.target.checked)}
            />
            <span>
              Li e autorizo a Doktor Assistant a executar essas ações quando forem
              solicitadas por voz.
            </span>
          </label>
        )}
      </div>
    </Dialog>
  );
}
