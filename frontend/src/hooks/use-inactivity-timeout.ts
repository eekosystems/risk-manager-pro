import { useCallback, useEffect, useRef } from "react";

const INACTIVITY_TIMEOUT_MS = 60 * 60 * 1000; // 60 minutes
// L-7: warn the user this far ahead of the silent logout so they can stay signed in.
const WARNING_BEFORE_MS = 2 * 60 * 1000; // 2 minutes
const ACTIVITY_EVENTS: (keyof DocumentEventMap)[] = [
  "mousedown",
  "mousemove",
  "keydown",
  "scroll",
  "touchstart",
];

interface UseInactivityTimeoutOptions {
  onTimeout: () => void;
  /** L-7: fired `warningMs` before logout with the seconds remaining. */
  onWarning?: (secondsRemaining: number) => void;
  /** L-7: fired when activity resumes after a warning was shown, so the UI can dismiss it. */
  onActive?: () => void;
  timeoutMs?: number;
  warningMs?: number;
}

export function useInactivityTimeout({
  onTimeout,
  onWarning,
  onActive,
  timeoutMs = INACTIVITY_TIMEOUT_MS,
  warningMs = WARNING_BEFORE_MS,
}: UseInactivityTimeoutOptions): void {
  const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const warnTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const warnedRef = useRef(false);

  const onTimeoutRef = useRef(onTimeout);
  onTimeoutRef.current = onTimeout;
  const onWarningRef = useRef(onWarning);
  onWarningRef.current = onWarning;
  const onActiveRef = useRef(onActive);
  onActiveRef.current = onActive;

  const resetTimer = useCallback(() => {
    if (timerRef.current !== null) clearTimeout(timerRef.current);
    if (warnTimerRef.current !== null) clearTimeout(warnTimerRef.current);

    // If a warning was on screen and the user is active again, dismiss it.
    if (warnedRef.current) {
      warnedRef.current = false;
      onActiveRef.current?.();
    }

    warnTimerRef.current = setTimeout(() => {
      warnedRef.current = true;
      onWarningRef.current?.(Math.round(warningMs / 1000));
    }, Math.max(0, timeoutMs - warningMs));

    timerRef.current = setTimeout(() => {
      onTimeoutRef.current();
    }, timeoutMs);
  }, [timeoutMs, warningMs]);

  useEffect(() => {
    resetTimer();

    for (const event of ACTIVITY_EVENTS) {
      document.addEventListener(event, resetTimer, { passive: true });
    }

    return () => {
      if (timerRef.current !== null) clearTimeout(timerRef.current);
      if (warnTimerRef.current !== null) clearTimeout(warnTimerRef.current);
      for (const event of ACTIVITY_EVENTS) {
        document.removeEventListener(event, resetTimer);
      }
    };
  }, [resetTimer]);
}
