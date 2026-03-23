import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { clsx } from "clsx";
import {
  AlertTriangle,
  BarChart3,
  Copy,
  Database,
  Loader2,
  MessageSquareCode,
  RotateCcw,
  Save,
  Shield,
} from "lucide-react";

import {
  getSettingsByCategory,
  updatePromptsSettings,
  type PromptsSettings,
} from "@/api/settings";
import { SettingsSection } from "@/components/settings/settings-section";
import {
  DEFAULT_INDEXING_INSTRUCTIONS,
  DEFAULT_PHL_PROMPT,
  DEFAULT_SRA_PROMPT,
  DEFAULT_SYSTEM_ANALYSIS_PROMPT,
  DEFAULT_SYSTEM_PROMPT,
} from "@/constants/default-prompts";

const FALLBACK_PROMPTS: PromptsSettings = {
  system_prompt: DEFAULT_SYSTEM_PROMPT,
  phl_prompt: DEFAULT_PHL_PROMPT,
  sra_prompt: DEFAULT_SRA_PROMPT,
  system_analysis_prompt: DEFAULT_SYSTEM_ANALYSIS_PROMPT,
  indexing_instructions: DEFAULT_INDEXING_INSTRUCTIONS,
};

type PromptKey = keyof PromptsSettings;

interface PromptSection {
  key: PromptKey;
  label: string;
  description: string;
  icon: typeof Shield;
}

const PROMPT_SECTIONS: PromptSection[] = [
  {
    key: "system_prompt",
    label: "System Prompt",
    description:
      "Base instructions sent with every conversation. Defines the AI personality and core behavior.",
    icon: MessageSquareCode,
  },
  {
    key: "phl_prompt",
    label: "PHL — Preliminary Hazard List",
    description:
      "Instructions for the Preliminary Hazard List assessment function.",
    icon: AlertTriangle,
  },
  {
    key: "sra_prompt",
    label: "SRA — Safety Risk Assessment",
    description:
      "Instructions for the Safety Risk Assessment function.",
    icon: Shield,
  },
  {
    key: "system_analysis_prompt",
    label: "System Analysis",
    description:
      "Instructions for the System Analysis function.",
    icon: BarChart3,
  },
  {
    key: "indexing_instructions",
    label: "Vector DB / Indexing",
    description:
      "Indexing requirements, document tagging conventions, source hierarchy, and dev partner handoff specifications for the vector database.",
    icon: Database,
  },
];

export function PromptsTab() {
  const queryClient = useQueryClient();
  const [prompts, setPrompts] = useState<PromptsSettings>(FALLBACK_PROMPTS);
  const [activePrompt, setActivePrompt] = useState<PromptKey>("system_prompt");
  const [copied, setCopied] = useState(false);

  const { data, isLoading, isError } = useQuery({
    queryKey: ["settings", "prompts"],
    queryFn: () => getSettingsByCategory<PromptsSettings>("prompts"),
    retry: false,
  });

  // The backend always returns the effective prompts (org overrides or server defaults),
  // so we use the API response as the source of truth for both display and reset.
  const serverPrompts = data?.settings
    ? data.settings
    : null;

  useEffect(() => {
    if (serverPrompts) {
      setPrompts(serverPrompts);
    }
  }, [serverPrompts]);

  const mutation = useMutation({
    mutationFn: updatePromptsSettings,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings", "prompts"] });
    },
  });

  function handleReset(key: PromptKey) {
    if (serverPrompts) {
      setPrompts((prev) => ({ ...prev, [key]: serverPrompts[key] }));
    }
  }

  function handleCopy() {
    void navigator.clipboard.writeText(prompts[activePrompt]);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  const activeSection = PROMPT_SECTIONS.find((s) => s.key === activePrompt);

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }


  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Prompt Configuration</h2>
        <p className="text-sm text-slate-500">
          Configure the system prompt and function-specific prompts that guide AI responses.
        </p>
      </div>

      {isError && (
        <div className="mb-4 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-700">
          <span className="font-semibold">Could not load prompts from the server.</span>{" "}
          The backend may be unavailable. Default prompts are configured server-side and will still be used by the AI.
        </div>
      )}

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
        <SettingsSection>
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
        </SettingsSection>
      )}

      {/* Save Button */}
      <div className="mt-6">
        <button
          onClick={() => mutation.mutate(prompts)}
          disabled={mutation.isPending}
          className="flex items-center gap-2 rounded-xl gradient-brand px-6 py-3 text-sm font-semibold text-white shadow-md shadow-brand-500/20 transition-all hover:shadow-lg hover:shadow-brand-500/30 disabled:opacity-50"
        >
          {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
          {mutation.isSuccess ? "Saved!" : mutation.isPending ? "Saving..." : "Save All Prompts"}
        </button>
        {mutation.isError && (
          <p className="mt-2 text-sm text-red-500">Failed to save. Please try again.</p>
        )}
      </div>
    </div>
  );
}
