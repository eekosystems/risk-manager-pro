import type { FunctionType } from "@/types/api";

export interface Followup {
  mode: FunctionType;
  label: string;
  prefill: string;
}

const MODE_MAP: Record<string, FunctionType> = {
  general: "general",
  system: "system",
  system_analysis: "system",
  phl: "phl",
  sra: "sra",
  risk_register: "risk_register",
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
    if (parts.length < 3) continue;
    const [modeRaw, label, ...prefillParts] = parts;
    if (!modeRaw || !label) continue;
    const mode = MODE_MAP[modeRaw.toLowerCase()];
    if (!mode) continue;
    const prefill = prefillParts.join(" | ").trim();
    if (!prefill) continue;
    followups.push({ mode, label, prefill });
  }

  const cleaned = content.slice(0, match.index).trimEnd();
  return { content: cleaned, followups: followups.slice(0, 4) };
}

export function stripFollowupsBlock(content: string): string {
  return content.replace(FOLLOWUPS_RE, "").trimEnd();
}
