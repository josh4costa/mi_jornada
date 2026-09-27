import React, { useEffect, useRef, useId } from 'react';
import Button from './Button';

interface ModalProps {
  isOpen: boolean;
  title: string;
  children: React.ReactNode;
  onClose: () => void;
  onConfirm?: () => void;
  confirmText?: string;
  cancelText?: string;
  confirmVariant?: 'primary' | 'danger' | 'success';
  loading?: boolean;
}

const Modal: React.FC<ModalProps> = ({
  isOpen,
  title,
  children,
  onClose,
  onConfirm,
  confirmText = 'Confirmar',
  cancelText = 'Cancelar',
  confirmVariant = 'primary',
  loading = false
}) => {
  const dialog = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const closeRef = useRef(onClose);
  const loadingRef = useRef(loading);
  closeRef.current = onClose;
  loadingRef.current = loading;
  useEffect(() => {
    if (!isOpen) return;
    const previous = document.activeElement as HTMLElement | null;
    document.body.classList.add('modal-open');
    const focusable = () => Array.from(dialog.current?.querySelectorAll<HTMLElement>('button:not(:disabled), input:not(:disabled), select:not(:disabled), textarea:not(:disabled), a[href], [tabindex="0"]') ?? []);
    (focusable()[0] ?? dialog.current)?.focus();
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === 'Escape' && !loadingRef.current) {
        event.preventDefault();
        closeRef.current();
      }
      if (event.key === 'Tab') {
        const elements = focusable();
        const first = elements[0];
        const last = elements[elements.length - 1];
        if (!first) { event.preventDefault(); dialog.current?.focus(); }
        else if (event.shiftKey && (document.activeElement === first || document.activeElement === dialog.current)) { event.preventDefault(); last.focus(); }
        else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first.focus(); }
      }
    };
    document.addEventListener('keydown', onKeyDown);
    return () => {
      document.removeEventListener('keydown', onKeyDown);
      document.body.classList.remove('modal-open');
      previous?.focus();
    };
  }, [isOpen]);

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-slate-900/50 backdrop-blur-sm">
      <div ref={dialog} role="dialog" aria-modal="true" aria-labelledby={titleId} aria-busy={loading} tabIndex={-1} className="bg-surface w-full max-w-md rounded-xl shadow-lg flex flex-col max-h-[90vh]">
        <div className="px-6 py-4 border-b border-slate-200">
          <h2 id={titleId} className="text-xl font-bold text-text">{title}</h2>
        </div>
        <div className="px-6 py-4 overflow-y-auto">
          {children}
        </div>
        <div className="px-6 py-4 border-t border-slate-200 flex flex-col sm:flex-row justify-end gap-3">
          <Button variant="ghost" onClick={onClose} disabled={loading} size="md">
            {cancelText}
          </Button>
          {onConfirm && (
            <Button variant={confirmVariant} onClick={onConfirm} loading={loading} size="md">
              {confirmText}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
};

export default Modal;
