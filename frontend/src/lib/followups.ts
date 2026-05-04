import type { FunctionType } from "@/types/api";

export type Followup =
  | {
      kind: "send";
      mode: FunctionType;
      label: string;
      prefill: string;
    }
  | {
      kind: "navigate";
      target: "risk-register";
      label: string;
    };

const MODE_MAP: Record<string, FunctionType> = {
  general: "general",
  system: "system",
  system_analysis: "system",
  phl: "phl",
  sra: "sra",
  risk_register: "risk_register",
};

const NAV_MAP: Record<string, "risk-register"> = {
  view_risk_register: "risk-register",
};

const FOLLOWUPS_RE = /<followups>([\s\S]*?)<\/followups>\s*$/i;

export function extractFollowups(content: string): {
  content: string;
  followups: Followup[];
} {
  const match = content.match(FOLLOWUPS_RE);
  if (!match || match.index === undefined) {
    return { content, followups: [] };
  }

  const block = match[1] ?? "";
  const followups: Followup[] = [];
  for (const rawLine of block.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    const parts = line.split("|").map((p) => p.trim());
    if (parts.length < 2) continue;
    const [modeRaw, label, ...prefillParts] = parts;
    if (!modeRaw || !label) continue;
    const modeKey = modeRaw.toLowerCase();

    const navTarget = NAV_MAP[modeKey];
    if (navTarget) {
      followups.push({ kind: "navigate", target: navTarget, label });
      continue;
    }

    const mode = MODE_MAP[modeKey];
    if (!mode) continue;
    const prefill = prefillParts.join(" | ").trim();
    if (!prefill) continue;
    followups.push({ kind: "send", mode, label, prefill });
  }

  const cleaned = content.slice(0, match.index).trimEnd();
  return { content: cleaned, followups: followups.slice(0, 4) };
}

export function stripFollowupsBlock(content: string): string {
  return content.replace(FOLLOWUPS_RE, "").trimEnd();
}

// The PHL prompt asks the model to emit a `<rr_payload>...</rr_payload>` block
// containing structured JSON for ingestion into the Risk Register. That block
// is for downstream tooling — the user should never see it in chat. Strip it
// (and any leading fenced-code wrapper the model occasionally adds around it)
// before rendering.
const RR_PAYLOAD_RE =
  /(?:```[a-zA-Z]*\s*)?<rr_payload>[\s\S]*?<\/rr_payload>(?:\s*```)?/gi;

export function stripRrPayloadBlock(content: string): string {
  return content.replace(RR_PAYLOAD_RE, "").trimEnd();
}
