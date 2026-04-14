/**
 * FAA SMS 5x5 Risk Matrix types and constants.
 *
 * Severity: stored as 1=Minimal → 5=Catastrophic. Displayed as 5=Minimal →
 * 1=Catastrophic (short field holds the display number, 6 - stored value).
 * Likelihood: rows (A=Frequent → E=Extremely Improbable)
 * Risk levels follow FAA Order 8040.4B guidelines.
 */

export type Severity = 1 | 2 | 3 | 4 | 5;
export type Likelihood = "A" | "B" | "C" | "D" | "E";
export type RiskLevel = "low" | "medium" | "high";

export interface RiskMatrixSelection {
  severity: Severity;
  likelihood: Likelihood;
  riskLevel: RiskLevel;
}

export const SEVERITY_LABELS: Record<Severity, { short: string; full: string }> = {
  1: { short: "5", full: "Minimal" },
  2: { short: "4", full: "Minor" },
  3: { short: "3", full: "Major" },
  4: { short: "2", full: "Hazardous" },
  5: { short: "1", full: "Catastrophic" },
};

export const LIKELIHOOD_LABELS: Record<Likelihood, { short: string; full: string }> = {
  A: { short: "A", full: "Frequent" },
  B: { short: "B", full: "Probable" },
  C: { short: "C", full: "Remote" },
  D: { short: "D", full: "Extremely Remote" },
  E: { short: "E", full: "Extremely Improbable" },
};

/**
 * 5x5 risk matrix mapping: RISK_MATRIX[likelihood][severity] → RiskLevel
 * Per FAA SMS guidelines (Order 8040.4B).
 */
export const RISK_MATRIX: Record<Likelihood, Record<Severity, RiskLevel>> = {
  A: { 1: "medium",  2: "high",   3: "high",    4: "high",    5: "high"    },
  B: { 1: "low",     2: "medium", 3: "high",    4: "high",    5: "high"    },
  C: { 1: "low",     2: "low",    3: "medium",  4: "high",    5: "high"    },
  D: { 1: "low",     2: "low",    3: "medium",  4: "medium",  5: "high"    },
  E: { 1: "low",     2: "low",    3: "low",     4: "low",     5: "medium"  },
};

export const RISK_LEVEL_CONFIG: Record<
  RiskLevel,
  { label: string; color: string; bg: string; border: string }
> = {
  low:     { label: "Low",     color: "text-green-800",  bg: "bg-green-100",  border: "border-green-300"  },
  medium:  { label: "Medium",  color: "text-yellow-800", bg: "bg-yellow-100", border: "border-yellow-300" },
  high:    { label: "High",    color: "text-red-800",    bg: "bg-red-100",    border: "border-red-300"    },
};

export interface RiskPositionCount {
  severity: Severity;
  likelihood: Likelihood;
  count: number;
}

export const SEVERITIES: Severity[] = [1, 2, 3, 4, 5];
export const LIKELIHOODS: Likelihood[] = ["A", "B", "C", "D", "E"];
