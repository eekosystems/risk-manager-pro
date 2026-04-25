import { useMemo } from "react";

import type { ChatMessage, FunctionType } from "@/types/api";

interface FieldMarker {
  key: string;
  label: string;
  patterns: RegExp[];
}

const FIELD_MARKERS: Record<FunctionType, FieldMarker[]> = {
  phl: [
    {
      key: "hazard",
      label: "Hazard described",
      patterns: [/\bhazard\s*(description)?\s*[:-]/i, /\*\*hazard\*\*/i],
    },
    {
      key: "category",
      label: "5M / ICAO category",
      patterns: [/\b(5M|ICAO)\s*(category|model)?\s*[:-]/i, /\bcategory\s*[:-]/i],
    },
    {
      key: "outcome",
      label: "Credible outcome",
      patterns: [/\bcredible\s+outcome\s*[:-]/i, /\boutcome\s*[:-]/i],
    },
    {
      key: "controls",
      label: "Existing controls",
      patterns: [/\bexisting\s+controls?\s*[:-]/i, /\bcontrols?\s*[:-]/i],
    },
  ],
  sra: [
    {
      key: "hazard",
      label: "Hazard identified",
      patterns: [/\bhazard\s*(description)?\s*[:-]/i, /\*\*hazard\*\*/i],
    },
    {
      key: "severity",
      label: "Severity scored",
      patterns: [/\bseverity\s*[:-]/i, /severity\s*level/i],
    },
    {
      key: "likelihood",
      label: "Likelihood scored",
      patterns: [/\blikelihood\s*[:-]/i, /\bprobability\s*[:-]/i],
    },
    {
      key: "risk",
      label: "Risk level computed",
      patterns: [/\brisk\s+level\s*[:-]/i, /\brisk\s+rating\s*[:-]/i],
    },
    {
      key: "mitigations",
      label: "Mitigations proposed",
      patterns: [/\bmitigations?\s*[:-]/i, /\brisk\s+treatment\s*[:-]/i],
    },
  ],
  risk_register: [
    {
      key: "airport",
      label: "Airport identified",
      patterns: [/\bairport\s*[:-]/i, /\bICAO\s+code\s*[:-]/i],
    },
    {
      key: "hazard",
      label: "Hazard described",
      patterns: [/\bhazard\s*(description)?\s*[:-]/i, /\*\*hazard\*\*/i],
    },
    {
      key: "domain",
      label: "Operational domain",
      patterns: [/\boperational\s+domain\s*[:-]/i, /\bdomain\s*[:-]/i],
    },
    {
      key: "category",
      label: "5M / ICAO category",
      patterns: [/\b(5M|ICAO)\s*(category|model)?\s*[:-]/i, /\bcategory\s*[:-]/i],
    },
    {
      key: "score",
      label: "Risk score",
      patterns: [/\brisk\s+score\s*[:-]/i, /\brisk\s+level\s*[:-]/i],
    },
    {
      key: "controls",
      label: "Existing controls",
      patterns: [/\bexisting\s+controls?\s*[:-]/i, /\bcontrols?\s*[:-]/i],
    },
    {
      key: "mitigations",
      label: "Mitigation actions",
      patterns: [/\bmitigations?\s*[:-]/i, /\bmitigation\s+actions?\s*[:-]/i],
    },
  ],
  system: [],
  general: [],
};

interface AssessmentStepperProps {
  functionType: FunctionType;
  messages: ChatMessage[];
}

export function AssessmentStepper({ functionType, messages }: AssessmentStepperProps) {
  const markers = FIELD_MARKERS[functionType];

  const captured = useMemo(() => {
    if (!markers.length) return new Set<string>();
    const haystack = messages
      .filter((m) => m.role === "assistant")
      .map((m) => m.content)
      .join("\n\n");
    const found = new Set<string>();
    for (const marker of markers) {
      if (marker.patterns.some((p) => p.test(haystack))) {
        found.add(marker.key);
      }
    }
    return found;
  }, [markers, messages]);

  if (!markers.length) return null;

  const completed = captured.size;
  const total = markers.length;

  return (
    <aside className="rounded-lg border border-slate-200 bg-white p-4">
      <div className="mb-3 flex items-baseline justify-between">
        <h3 className="text-sm font-semibold text-slate-900">Assessment progress</h3>
        <span className="text-xs text-slate-500">
          {completed}/{total}
        </span>
      </div>
      <ol className="space-y-2">
        {markers.map((marker) => {
          const done = captured.has(marker.key);
          return (
            <li key={marker.key} className="flex items-start gap-2 text-xs">
              <span
                aria-hidden="true"
                className={
                  "mt-0.5 inline-flex h-4 w-4 flex-shrink-0 items-center justify-center rounded-full border " +
                  (done
                    ? "border-green-500 bg-green-500 text-white"
                    : "border-slate-300 bg-white text-slate-300")
                }
              >
                {done ? "✓" : ""}
              </span>
              <span className={done ? "text-slate-900" : "text-slate-500"}>{marker.label}</span>
            </li>
          );
        })}
      </ol>
    </aside>
  );
}
