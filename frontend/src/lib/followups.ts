import type { FunctionType } from "@/types/api";

export type FollowupSlot =
  | "forward"
  | "confirm"
  | "validate"
  | "revise"
  | "clarify"
  | "explore";

export type Followup =
  | {
      kind: "send";
      slot?: FollowupSlot;
      mode: FunctionType;
      label: string;
      prefill: string;
    }
  | {
      kind: "navigate";
      slot?: FollowupSlot;
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

const SLOT_SET: ReadonlySet<FollowupSlot> = new Set([
  "forward",
  "confirm",
  "validate",
  "revise",
  "clarify",
  "explore",
]);

// Stable display order: Forward top-left, Confirm/Validate top-right,
// contextual chips on the bottom row.
const SLOT_ORDER: Record<FollowupSlot, number> = {
  forward: 0,
  confirm: 1,
  validate: 1,
  revise: 2,
  clarify: 3,
  explore: 4,
};

const FOLLOWUPS_RE = /<followups>([\s\S]*?)<\/followups>\s*$/i;

function parseSlot(token: string): FollowupSlot | null {
  const t = token.toLowerCase();
  return SLOT_SET.has(t as FollowupSlot) ? (t as FollowupSlot) : null;
}

function buildFollowup(
  slot: FollowupSlot | undefined,
  modeRaw: string,
  label: string,
  prefillParts: string[],
): Followup | null {
  const modeKey = modeRaw.toLowerCase();

  const navTarget = NAV_MAP[modeKey];
  if (navTarget) {
    return slot
      ? { kind: "navigate", slot, target: navTarget, label }
      : { kind: "navigate", target: navTarget, label };
  }

  const mode = MODE_MAP[modeKey];
  if (!mode) return null;
  const prefill = prefillParts.join(" | ").trim();
  if (!prefill) return null;
  return slot
    ? { kind: "send", slot, mode, label, prefill }
    : { kind: "send", mode, label, prefill };
}

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
  let anySlot = false;

  for (const rawLine of block.split("\n")) {
    const line = rawLine.trim();
    if (!line) continue;
    const parts = line.split("|").map((p) => p.trim());
    if (parts.length < 2) continue;

    // Detect new 4-field format (slot | mode | label | prefill) by checking
    // whether the first token is a known slot name. Otherwise fall back to
    // the legacy 3-field format (mode | label | prefill).
    const maybeSlot = parseSlot(parts[0] ?? "");
    let followup: Followup | null;
    if (maybeSlot && parts.length >= 3) {
      const [, modeRaw, label, ...prefillParts] = parts;
      if (!modeRaw || !label) continue;
      followup = buildFollowup(maybeSlot, modeRaw, label, prefillParts);
      if (followup) anySlot = true;
    } else {
      const [modeRaw, label, ...prefillParts] = parts;
      if (!modeRaw || !label) continue;
      followup = buildFollowup(undefined, modeRaw, label, prefillParts);
    }

    if (followup) followups.push(followup);
  }

  // Stable sort by slot order so Forward renders top-left, Confirm/Validate
  // top-right, contextual chips on the bottom row. Skip when no slots were
  // emitted (legacy format) — preserve the model's ordering.
  if (anySlot) {
    followups.sort((a, b) => {
      const ao = a.slot ? SLOT_ORDER[a.slot] : 99;
      const bo = b.slot ? SLOT_ORDER[b.slot] : 99;
      return ao - bo;
    });
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
