import { useEffect, useRef } from "react";

import { useImportSrmdHazards } from "@/hooks/use-risks";
import { useToast } from "@/hooks/use-toast";

interface AutoImportSrmdHazardsOptions {
  /** True once an editor's register and a finished scan are both loaded. */
  enabled: boolean;
  /** Scan hazards that are not on the register yet. */
  unimportedCount: number;
  lastScanCompletedAt: number | null;
}

/**
 * Saves SharePoint SRMD hazards to the Risk Register as soon as the scan
 * holds ones that are not on it yet, so their mitigations can be edited
 * without a manual import step.
 */
export function useAutoImportSrmdHazards({
  enabled,
  unimportedCount,
  lastScanCompletedAt,
}: AutoImportSrmdHazardsOptions): { isImporting: boolean } {
  const { mutate, isPending } = useImportSrmdHazards();
  const { addToast } = useToast();
  // One attempt per scan result: hazards this account cannot import stay
  // unimported and must not trigger the import again on every render.
  const lastAttempt = useRef<string | null>(null);

  useEffect(() => {
    if (!enabled || unimportedCount === 0 || isPending) return;
    const attempt = `${lastScanCompletedAt}:${unimportedCount}`;
    if (lastAttempt.current === attempt) return;
    lastAttempt.current = attempt;
    mutate(undefined, {
      onSuccess: (result) => {
        if (result.imported > 0) {
          addToast(
            `Added ${result.imported} SRMD ${result.imported === 1 ? "hazard" : "hazards"} to the register`,
            "info",
          );
        }
      },
      onError: () => addToast("Could not add the SRMD hazards to the register", "error"),
    });
  }, [enabled, unimportedCount, lastScanCompletedAt, isPending, mutate, addToast]);

  return { isImporting: isPending };
}
