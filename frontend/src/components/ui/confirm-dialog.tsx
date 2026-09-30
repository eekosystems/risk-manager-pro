import { useEffect, useId, useRef } from "react";

import { Button } from "./button";

interface ConfirmDialogProps {
  title: string;
  description: string;
  confirmLabel: string;
  cancelLabel?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  cancelLabel = "Cancel",
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  const overlayRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const descriptionId = useId();

  useEffect(() => {
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onCancel();
    }
    document.addEventListener("keydown", handleKey);
    return () => document.removeEventListener("keydown", handleKey);
  }, [onCancel]);

  function handleOverlayClick(e: React.MouseEvent) {
    if (e.target === overlayRef.current) onCancel();
  }

  return (
    <div
      ref={overlayRef}
      onClick={handleOverlayClick}
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      role="alertdialog"
      aria-modal="true"
      aria-labelledby={titleId}
      aria-describedby={descriptionId}
    >
      <div className="w-full max-w-md rounded-2xl border border-gray-200 bg-white p-6 shadow-2xl">
        <h3 id={titleId} className="text-sm font-semibold text-gray-900">
          {title}
        </h3>
        <p id={descriptionId} className="mt-2 break-words text-[13px] text-slate-600">
          {description}
        </p>
        <div className="mt-5 flex justify-end gap-2">
          {/* Focus starts on cancel so a stray Enter cannot confirm. */}
          <Button variant="secondary" size="sm" autoFocus onClick={onCancel}>
            {cancelLabel}
          </Button>
          <Button variant="danger" size="sm" onClick={onConfirm}>
            {confirmLabel}
          </Button>
        </div>
      </div>
    </div>
  );
}
