'use client';

import { useCallback, useEffect, useRef, type ReactNode } from 'react';
import { X } from 'lucide-react';

/* Diálogo modal compartilhado pelos três painéis do assistente.
 *
 * Antes desta extração cada um se comportava de um jeito: o de permissão fechava
 * com Escape e no backdrop, o de configuração não fechava por nenhum dos dois, e o
 * Voice Lab só pelo X. Nenhum deles cuidava do foco.
 *
 * `aria-modal="true"` faz o leitor de tela ocultar o resto da página, mas NÃO prende
 * o foco do teclado: sem o laço abaixo, o Tab sai do diálogo e continua acionando os
 * botões atrás dele, invisíveis para quem navega assim. Isso importa mais aqui do que
 * na média, porque um destes diálogos autoriza a execução de comandos com os
 * privilégios da conta do usuário.
 */

const FOCAVEIS = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',');

export type DialogProps = {
  /** Título acessível; vira o `aria-labelledby` pelo id derivado. */
  id: string;
  titulo: string;
  kicker?: string;
  icone?: ReactNode;
  children: ReactNode;
  rodape?: ReactNode;
  /** Ausente = diálogo sem saída (onboarding obrigatório): sem X, Escape ou backdrop. */
  aoFechar?: () => void;
  className?: string;
};

export function Dialog({
  id,
  titulo,
  kicker,
  icone,
  children,
  rodape,
  aoFechar,
  className,
}: DialogProps) {
  const painel = useRef<HTMLElement>(null);
  const focoAnterior = useRef<HTMLElement | null>(null);

  const focaveis = useCallback(
    () =>
      Array.from(painel.current?.querySelectorAll<HTMLElement>(FOCAVEIS) ?? []).filter(
        (elemento) => elemento.offsetParent !== null || elemento === document.activeElement,
      ),
    [],
  );

  // Guarda quem abriu, move o foco para dentro e devolve ao desmontar. Sem isto o
  // foco continua no botão que abriu o diálogo, atrás do backdrop.
  useEffect(() => {
    focoAnterior.current = document.activeElement as HTMLElement | null;
    const alvo = focaveis()[0] ?? painel.current;
    alvo?.focus();
    return () => focoAnterior.current?.focus?.();
  }, [focaveis]);

  useEffect(() => {
    function aoTeclar(evento: KeyboardEvent) {
      if (evento.key === 'Escape' && aoFechar) {
        evento.stopPropagation();
        aoFechar();
        return;
      }

      if (evento.key !== 'Tab') return;

      const lista = focaveis();
      if (lista.length === 0) {
        evento.preventDefault();
        return;
      }

      const primeiro = lista[0];
      const ultimo = lista[lista.length - 1];
      const atual = document.activeElement;

      // Fecha o laço nas duas pontas: Tab no último volta ao primeiro e
      // Shift+Tab no primeiro vai ao último.
      if (!evento.shiftKey && atual === ultimo) {
        evento.preventDefault();
        primeiro.focus();
      } else if (evento.shiftKey && (atual === primeiro || !painel.current?.contains(atual))) {
        evento.preventDefault();
        ultimo.focus();
      }
    }

    document.addEventListener('keydown', aoTeclar, true);
    return () => document.removeEventListener('keydown', aoTeclar, true);
  }, [aoFechar, focaveis]);

  return (
    <div
      className="permission-backdrop"
      role="presentation"
      onMouseDown={(evento) => {
        if (aoFechar && evento.target === evento.currentTarget) aoFechar();
      }}
    >
      <section
        ref={painel}
        className={className ? `permission-dialog ${className}` : 'permission-dialog'}
        role="dialog"
        aria-modal="true"
        aria-labelledby={`${id}-title`}
        tabIndex={-1}
      >
        <header className="permission-header">
          {icone && (
            <span className="permission-icon" aria-hidden="true">
              {icone}
            </span>
          )}
          <div>
            {kicker && <p className="panel-kicker">{kicker}</p>}
            <h2 id={`${id}-title`}>{titulo}</h2>
          </div>
          {aoFechar && (
            <button
              className="icon-button"
              type="button"
              onClick={aoFechar}
              aria-label={`Fechar ${titulo.toLowerCase()}`}
              title="Fechar"
            >
              <X aria-hidden="true" />
            </button>
          )}
        </header>

        {children}

        {rodape}
      </section>
    </div>
  );
}
