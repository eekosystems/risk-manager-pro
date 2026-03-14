import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Brain, Loader2, Save, Thermometer, Zap } from "lucide-react";

import {
  getSettingsByCategory,
  updateModelSettings,
  type ModelSettings,
} from "@/api/settings";
import { SettingsSection } from "@/components/settings/settings-section";

const DEFAULT_CONFIG: ModelSettings = {
  chat_model: "gpt-4o",
  temperature: 0.3,
  max_output_tokens: 4096,
  top_p: 0.95,
  frequency_penalty: 0,
  presence_penalty: 0,
  stream_responses: true,
};

const AVAILABLE_MODELS = [
  {
    id: "gpt-4o",
    name: "GPT-4o",
    description: "Most capable model, best for complex safety analysis",
    contextWindow: "128K",
  },
  {
    id: "gpt-4o-mini",
    name: "GPT-4o Mini",
    description: "Faster and cheaper, good for simple queries",
    contextWindow: "128K",
  },
  {
    id: "gpt-4-turbo",
    name: "GPT-4 Turbo",
    description: "Previous generation, stable performance",
    contextWindow: "128K",
  },
];

export function ModelPreferencesTab() {
  const queryClient = useQueryClient();
  const [config, setConfig] = useState<ModelSettings>(DEFAULT_CONFIG);

  const { data, isLoading } = useQuery({
    queryKey: ["settings", "model"],
    queryFn: () => getSettingsByCategory<ModelSettings>("model"),
    retry: false,
  });

  useEffect(() => {
    if (data?.settings) {
      setConfig(data.settings);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: updateModelSettings,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings", "model"] });
    },
  });

  function updateConfig<K extends keyof ModelSettings>(key: K, value: ModelSettings[K]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

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
        <h2 className="text-lg font-bold text-slate-900">Model Preferences</h2>
        <p className="text-sm text-slate-500">
          Choose your AI model and configure generation parameters.
        </p>
      </div>

      {/* Model Selection */}
      <div className="mb-8"><SettingsSection>
        <div className="mb-5 flex items-center gap-2">
          <Brain size={18} className="text-brand-500" />
          <h3 className="text-sm font-bold text-slate-800">Chat Model</h3>
        </div>

        <div className="space-y-3">
          {AVAILABLE_MODELS.map((model) => (
            <button
              key={model.id}
              onClick={() => updateConfig("chat_model", model.id)}
              className={`w-full rounded-xl border p-4 text-left transition-all ${
                config.chat_model === model.id
                  ? "border-brand-500 bg-brand-50 shadow-sm shadow-brand-500/10"
                  : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
              }`}
            >
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm font-bold text-slate-800">
                      {model.name}
                    </span>
                    {config.chat_model === model.id && (
                      <span className="rounded-full gradient-brand px-2 py-0.5 text-[10px] font-bold text-white">
                        Active
                      </span>
                    )}
                  </div>
                  <p className="text-[12px] text-slate-500">{model.description}</p>
                </div>
                <span className="rounded-lg border border-gray-200 px-2.5 py-1 text-[11px] font-semibold text-slate-500">
                  {model.contextWindow}
                </span>
              </div>
            </button>
          ))}
        </div>
      </SettingsSection></div>

      {/* Generation Parameters */}
      <div className="mb-8"><SettingsSection>
        <div className="mb-5 flex items-center gap-2">
          <Thermometer size={18} className="text-brand-500" />
          <h3 className="text-sm font-bold text-slate-800">Generation Parameters</h3>
        </div>

        <div className="space-y-5">
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Temperature
            </label>
            <input
              type="range"
              min={0}
              max={200}
              value={config.temperature * 100}
              onChange={(e) =>
                updateConfig("temperature", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>Precise (0)</span>
              <span className="font-semibold text-brand-500">
                {config.temperature.toFixed(2)}
              </span>
              <span>Creative (2.0)</span>
            </div>
            <p className="mt-1 text-[12px] text-slate-400">
              Lower values produce more focused, deterministic responses. Recommended: 0.1-0.4 for safety analysis.
            </p>
          </div>

          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Top P
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={config.top_p * 100}
              onChange={(e) =>
                updateConfig("top_p", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>0</span>
              <span className="font-semibold text-brand-500">
                {config.top_p.toFixed(2)}
              </span>
              <span>1.0</span>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Max Output Tokens
            </label>
            <input
              type="number"
              value={config.max_output_tokens}
              onChange={(e) =>
                updateConfig("max_output_tokens", Number(e.target.value))
              }
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Frequency Penalty
            </label>
            <input
              type="range"
              min={0}
              max={200}
              value={config.frequency_penalty * 100}
              onChange={(e) =>
                updateConfig("frequency_penalty", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>0</span>
              <span className="font-semibold text-brand-500">
                {config.frequency_penalty.toFixed(2)}
              </span>
              <span>2.0</span>
            </div>
          </div>

          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Presence Penalty
            </label>
            <input
              type="range"
              min={0}
              max={200}
              value={config.presence_penalty * 100}
              onChange={(e) =>
                updateConfig("presence_penalty", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>0</span>
              <span className="font-semibold text-brand-500">
                {config.presence_penalty.toFixed(2)}
              </span>
              <span>2.0</span>
            </div>
          </div>

          <div className="flex items-center justify-between">
            <div>
              <span className="text-[13px] font-semibold text-slate-700">
                Stream Responses
              </span>
              <p className="text-[12px] text-slate-400">
                Show AI response as it generates (recommended)
              </p>
            </div>
            <button
              onClick={() =>
                updateConfig("stream_responses", !config.stream_responses)
              }
              className={`relative h-6 w-11 rounded-full transition-colors ${
                config.stream_responses ? "bg-brand-500" : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  config.stream_responses ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>
      </SettingsSection></div>

      {/* Preset buttons */}
      <div className="mb-8"><SettingsSection>
        <div className="mb-4 flex items-center gap-2">
          <Zap size={18} className="text-brand-500" />
          <h3 className="text-sm font-bold text-slate-800">Quick Presets</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() =>
              setConfig((prev) => ({
                ...prev,
                temperature: 0.1,
                top_p: 0.9,
                frequency_penalty: 0,
                presence_penalty: 0,
              }))
            }
            className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-all hover:border-brand-500 hover:bg-brand-50 hover:text-brand-600"
          >
            Safety Analysis (Conservative)
          </button>
          <button
            onClick={() =>
              setConfig((prev) => ({
                ...prev,
                temperature: 0.3,
                top_p: 0.95,
                frequency_penalty: 0,
                presence_penalty: 0,
              }))
            }
            className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-all hover:border-brand-500 hover:bg-brand-50 hover:text-brand-600"
          >
            Balanced (Default)
          </button>
          <button
            onClick={() =>
              setConfig((prev) => ({
                ...prev,
                temperature: 0.7,
                top_p: 1.0,
                frequency_penalty: 0.3,
                presence_penalty: 0.3,
              }))
            }
            className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-all hover:border-brand-500 hover:bg-brand-50 hover:text-brand-600"
          >
            Creative Brainstorming
          </button>
        </div>
      </SettingsSection></div>

      {/* Save Button */}
      <button
        onClick={() => mutation.mutate(config)}
        disabled={mutation.isPending}
        className="flex items-center gap-2 rounded-xl gradient-brand px-6 py-3 text-sm font-semibold text-white shadow-md shadow-brand-500/20 transition-all hover:shadow-lg hover:shadow-brand-500/30 disabled:opacity-50"
      >
        {mutation.isPending ? <Loader2 size={16} className="animate-spin" /> : <Save size={16} />}
        {mutation.isSuccess ? "Saved!" : mutation.isPending ? "Saving..." : "Save Changes"}
      </button>
      {mutation.isError && (
        <p className="mt-2 text-sm text-red-500">Failed to save. Please try again.</p>
      )}
    </div>
  );
}
