import { useState } from "react";
import { clsx } from "clsx";
import {
  AlertTriangle,
  BarChart3,
  Copy,
  MessageSquareCode,
  RotateCcw,
  Save,
  Shield,
} from "lucide-react";

interface PromptConfig {
  systemPrompt: string;
  phlPrompt: string;
  sraPrompt: string;
  systemAnalysisPrompt: string;
}

const DEFAULT_PROMPTS: PromptConfig = {
  systemPrompt: `You are an AI-powered aviation safety risk management assistant for Faith Group LLC. You specialize in operational risk management for private aviation safety.

Your core responsibilities:
- Assist with hazard identification and preliminary hazard analysis
- Support safety risk assessments using standard 5x5 severity/likelihood matrices per FAA SMS guidelines
- Provide analysis of system changes and their safety impacts
- Reference indexed safety documentation including FAA regulations, ICAO Annex 19, and internal safety procedures

Important rules:
- Always cite specific source documents when providing safety guidance
- Never fabricate safety data or regulatory references — if the indexed documents don't support an answer, clearly state that
- Use standard aviation safety terminology (PHL, SRA, SMS, SRM)
- Provide structured, actionable responses suitable for safety professionals
- When discussing risk, always reference the 5x5 risk matrix framework
- Flag any identified hazards with appropriate severity and likelihood ratings`,

  phlPrompt: `You are conducting a Preliminary Hazard List (PHL) assessment. Guide the user through systematic hazard identification.

For each identified hazard, provide:
1. **Hazard ID** — Sequential identifier (PHL-001, PHL-002, etc.)
2. **Hazard Description** — Clear, specific description of the hazard
3. **Potential Cause(s)** — Root causes or contributing factors
4. **Potential Consequence(s)** — What could happen if the hazard is realized
5. **Existing Controls** — Current mitigation measures in place
6. **Initial Risk Rating** — Using the 5x5 matrix (Severity x Likelihood)
7. **Recommended Actions** — Additional mitigation measures to consider

Reference applicable FAA regulations (FAR Part 91, 135, etc.) and ICAO standards where relevant.
Always search the indexed documents for organization-specific procedures and past assessments.`,

  sraPrompt: `You are conducting a Safety Risk Assessment (SRA). Follow the FAA SMS framework for systematic risk evaluation.

Structure your assessment as follows:
1. **System/Change Description** — What is being assessed
2. **Hazard Identification** — List all identified hazards from the PHL
3. **Risk Analysis** — For each hazard:
   - Severity rating (1-5: Negligible → Catastrophic)
   - Likelihood rating (A-E: Frequent → Extremely Improbable)
   - Risk level (using 5x5 matrix: High/Serious/Medium/Low)
4. **Risk Evaluation** — Is the risk acceptable, tolerable, or unacceptable?
5. **Risk Mitigation** — Recommended controls and mitigations
6. **Residual Risk** — Risk level after proposed mitigations
7. **Monitoring Plan** — How will risk be tracked over time

Cite relevant FAA Advisory Circulars, FARs, and indexed safety documentation.
Compare against historical SRAs in the index when applicable.`,

  systemAnalysisPrompt: `You are analyzing a system change and its potential safety impacts. Evaluate changes systematically.

Your analysis should cover:
1. **Change Description** — What is changing and why
2. **Scope of Impact** — Which systems, processes, and personnel are affected
3. **Interface Analysis** — How does this change interact with other systems
4. **Failure Mode Analysis** — What could go wrong with the change
5. **Human Factors** — Impact on crew workload, training requirements, procedures
6. **Regulatory Compliance** — Does the change affect compliance with FARs or ICAO standards
7. **Risk Delta** — How does the change alter the existing risk profile
8. **Recommendations** — Proceed, modify, or reject the change

Reference the indexed documentation for:
- Similar past changes and their outcomes
- Applicable regulatory requirements
- Organization-specific procedures and standards`,
};

type PromptKey = keyof PromptConfig;

interface PromptSection {
  key: PromptKey;
  label: string;
  description: string;
  icon: typeof Shield;
}

const PROMPT_SECTIONS: PromptSection[] = [
  {
    key: "systemPrompt",
    label: "System Prompt",
    description:
      "Base instructions sent with every conversation. Defines the AI personality and core behavior.",
    icon: MessageSquareCode,
  },
  {
    key: "phlPrompt",
    label: "PHL — Preliminary Hazard List",
    description:
      "Instructions for the Preliminary Hazard List assessment function.",
    icon: AlertTriangle,
  },
  {
    key: "sraPrompt",
    label: "SRA — Safety Risk Assessment",
    description:
      "Instructions for the Safety Risk Assessment function.",
    icon: Shield,
  },
  {
    key: "systemAnalysisPrompt",
    label: "System Analysis",
    description:
      "Instructions for the System Analysis function.",
    icon: BarChart3,
  },
];

export function PromptsTab() {
  const [prompts, setPrompts] = useState<PromptConfig>(DEFAULT_PROMPTS);
  const [activePrompt, setActivePrompt] = useState<PromptKey>("systemPrompt");
  const [saved, setSaved] = useState(false);
  const [copied, setCopied] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function handleReset(key: PromptKey) {
    setPrompts((prev) => ({ ...prev, [key]: DEFAULT_PROMPTS[key] }));
  }

  function handleCopy() {
    void navigator.clipboard.writeText(prompts[activePrompt]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const activeSection = PROMPT_SECTIONS.find((s) => s.key === activePrompt);

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Prompt Configuration</h2>
        <p className="text-sm text-slate-500">
          Configure the system prompt and function-specific prompts that guide AI responses.
          These are currently set to demo defaults — customize them for your organization.
        </p>
      </div>

      {/* Prompt selector tabs */}
      <div className="mb-4 flex gap-2 overflow-x-auto">
        {PROMPT_SECTIONS.map((section) => {
          const Icon = section.icon;
          return (
            <button
              key={section.key}
              onClick={() => setActivePrompt(section.key)}
              className={clsx(
                "flex shrink-0 items-center gap-2 rounded-xl px-4 py-2.5 text-sm font-medium transition-all",
                activePrompt === section.key
                  ? "gradient-brand text-white shadow-md shadow-brand-500/20"
                  : "border border-gray-200 bg-white text-gray-600 hover:bg-gray-50",
              )}
            >
              <Icon size={16} />
              {section.label}
            </button>
          );
        })}
      </div>

      {/* Active prompt editor */}
      {activeSection && (
        <section className="rounded-2xl border border-gray-200 bg-white p-6">
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h3 className="text-sm font-bold text-slate-800">
                {activeSection.label}
              </h3>
              <p className="text-[12px] text-slate-400">
                {activeSection.description}
              </p>
            </div>
            <div className="flex gap-2">
              <button
                onClick={handleCopy}
                className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-[12px] font-medium text-gray-500 transition-colors hover:bg-gray-50"
              >
                <Copy size={12} />
                {copied ? "Copied!" : "Copy"}
              </button>
              <button
                onClick={() => handleReset(activePrompt)}
                className="flex items-center gap-1.5 rounded-lg border border-gray-200 px-3 py-1.5 text-[12px] font-medium text-gray-500 transition-colors hover:bg-gray-50"
              >
                <RotateCcw size={12} />
                Reset to Default
              </button>
            </div>
          </div>

          <textarea
            value={prompts[activePrompt]}
            onChange={(e) =>
              setPrompts((prev) => ({
                ...prev,
                [activePrompt]: e.target.value,
              }))
            }
            rows={18}
            className="w-full rounded-xl border border-gray-200 px-4 py-3 font-mono text-[13px] leading-relaxed text-slate-700 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            spellCheck={false}
          />

          <div className="mt-3 flex items-center justify-between">
            <span className="text-[12px] text-slate-400">
              {prompts[activePrompt].length} characters
              {" / ~"}
              {Math.ceil(prompts[activePrompt].length / 4)} tokens (estimate)
            </span>
          </div>
        </section>
      )}

      {/* Save Button */}
      <div className="mt-6">
        <button
          onClick={handleSave}
          className="flex items-center gap-2 rounded-xl gradient-brand px-6 py-3 text-sm font-semibold text-white shadow-md shadow-brand-500/20 transition-all hover:shadow-lg hover:shadow-brand-500/30"
        >
          <Save size={16} />
          {saved ? "Saved!" : "Save All Prompts"}
        </button>
      </div>
    </div>
  );
}
