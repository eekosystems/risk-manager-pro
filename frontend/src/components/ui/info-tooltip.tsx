import { useEffect, useRef, useState } from "react";
import { HelpCircle } from "lucide-react";

interface InfoTooltipProps {
  content: React.ReactNode;
  label?: string;
  size?: number;
}

/**
 * A small "?" icon next to a label that opens a definitional popover on
 * hover (desktop) or click (touch). Built without a portal — positioned
 * absolutely relative to the trigger and clamped to the viewport with a
 * post-render adjustment so it never spills off the right edge of the
 * settings modal.
 *
 * Use this to explain non-obvious config knobs (RAG params, model
 * generation parameters, etc.) so end users can learn while configuring
 * rather than having to leave the app to look up terminology.
 */
export function InfoTooltip({ content, label, size = 13 }: InfoTooltipProps) {
  const [open, setOpen] = useState(false);
  const [openedByClick, setOpenedByClick] = useState(false);
  const wrapperRef = useRef<HTMLSpanElement | null>(null);
  const popoverRef = useRef<HTMLSpanElement | null>(null);
  const [shiftLeft, setShiftLeft] = useState(0);

  useEffect(() => {
    if (!open) return;
    const onDocClick = (e: MouseEvent) => {
      if (!wrapperRef.current) return;
      if (!wrapperRef.current.contains(e.target as Node)) {
        setOpen(false);
        setOpenedByClick(false);
      }
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setOpen(false);
        setOpenedByClick(false);
      }
    };
    document.addEventListener("mousedown", onDocClick);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDocClick);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  // After the popover renders, nudge it left if it would overflow the viewport.
  useEffect(() => {
    if (!open || !popoverRef.current) {
      setShiftLeft(0);
      return;
    }
    const rect = popoverRef.current.getBoundingClientRect();
    const overflow = rect.right - (window.innerWidth - 8);
    if (overflow > 0) setShiftLeft(overflow);
    else setShiftLeft(0);
  }, [open, content]);

  return (
    <span
      ref={wrapperRef}
      className="relative inline-flex items-center"
      onMouseEnter={() => {
        if (!openedByClick) setOpen(true);
      }}
      onMouseLeave={() => {
        if (!openedByClick) setOpen(false);
      }}
    >
      <button
        type="button"
        aria-label={label ?? "More information"}
        onClick={(e) => {
          e.stopPropagation();
          const next = !open || !openedByClick;
          setOpen(next);
          setOpenedByClick(next);
        }}
        className="inline-flex h-4 w-4 items-center justify-center rounded-full text-slate-400 transition-colors hover:text-brand-500 focus:text-brand-500 focus:outline-none"
      >
        <HelpCircle size={size} />
      </button>
      {open && (
        <span
          ref={popoverRef}
          role="tooltip"
          style={{ transform: `translateX(${-shiftLeft}px)` }}
          className="absolute left-5 top-1/2 z-50 -translate-y-1/2 w-64 rounded-lg border border-gray-200 bg-white p-3 text-[12px] font-normal leading-snug text-slate-600 shadow-xl"
        >
          {content}
        </span>
      )}
    </span>
  );
}
