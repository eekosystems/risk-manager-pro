import { useState } from "react";
import { Brain, Save, Thermometer, Zap } from "lucide-react";

interface ModelConfig {
  chatModel: string;
  temperature: number;
  maxOutputTokens: number;
  topP: number;
  frequencyPenalty: number;
  presencePenalty: number;
  streamResponses: boolean;
}

const DEFAULT_CONFIG: ModelConfig = {
  chatModel: "gpt-4o",
  temperature: 0.3,
  maxOutputTokens: 4096,
  topP: 0.95,
  frequencyPenalty: 0,
  presencePenalty: 0,
  streamResponses: true,
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
  const [config, setConfig] = useState<ModelConfig>(DEFAULT_CONFIG);
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function updateConfig<K extends keyof ModelConfig>(key: K, value: ModelConfig[K]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Model Preferences</h2>
        <p className="text-sm text-slate-500">
          Choose your AI model and configure generation parameters.
        </p>
      </div>

      {/* Model Selection */}
      <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-6">
        <div className="mb-5 flex items-center gap-2">
          <Brain size={18} className="text-brand-500" />
          <h3 className="text-sm font-bold text-slate-800">Chat Model</h3>
        </div>

        <div className="space-y-3">
          {AVAILABLE_MODELS.map((model) => (
            <button
              key={model.id}
              onClick={() => updateConfig("chatModel", model.id)}
              className={`w-full rounded-xl border p-4 text-left transition-all ${
                config.chatModel === model.id
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
                    {config.chatModel === model.id && (
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
      </section>

      {/* Generation Parameters */}
      <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-6">
        <div className="mb-5 flex items-center gap-2">
          <Thermometer size={18} className="text-brand-500" />
          <h3 className="text-sm font-bold text-slate-800">Generation Parameters</h3>
        </div>

        <div className="space-y-5">
          {/* Temperature */}
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

          {/* Top P */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Top P
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={config.topP * 100}
              onChange={(e) =>
                updateConfig("topP", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>0</span>
              <span className="font-semibold text-brand-500">
                {config.topP.toFixed(2)}
              </span>
              <span>1.0</span>
            </div>
          </div>

          {/* Max Output Tokens */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Max Output Tokens
            </label>
            <input
              type="number"
              value={config.maxOutputTokens}
              onChange={(e) =>
                updateConfig("maxOutputTokens", Number(e.target.value))
              }
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          {/* Frequency Penalty */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Frequency Penalty
            </label>
            <input
              type="range"
              min={0}
              max={200}
              value={config.frequencyPenalty * 100}
              onChange={(e) =>
                updateConfig("frequencyPenalty", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>0</span>
              <span className="font-semibold text-brand-500">
                {config.frequencyPenalty.toFixed(2)}
              </span>
              <span>2.0</span>
            </div>
          </div>

          {/* Presence Penalty */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Presence Penalty
            </label>
            <input
              type="range"
              min={0}
              max={200}
              value={config.presencePenalty * 100}
              onChange={(e) =>
                updateConfig("presencePenalty", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>0</span>
              <span className="font-semibold text-brand-500">
                {config.presencePenalty.toFixed(2)}
              </span>
              <span>2.0</span>
            </div>
          </div>

          {/* Stream Responses */}
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
                updateConfig("streamResponses", !config.streamResponses)
              }
              className={`relative h-6 w-11 rounded-full transition-colors ${
                config.streamResponses ? "bg-brand-500" : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  config.streamResponses ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>
      </section>

      {/* Preset buttons */}
      <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-6">
        <div className="mb-4 flex items-center gap-2">
          <Zap size={18} className="text-brand-500" />
          <h3 className="text-sm font-bold text-slate-800">Quick Presets</h3>
        </div>
        <div className="flex flex-wrap gap-2">
          <button
            onClick={() =>
              setConfig({
                ...config,
                temperature: 0.1,
                topP: 0.9,
                frequencyPenalty: 0,
                presencePenalty: 0,
              })
            }
            className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-all hover:border-brand-500 hover:bg-brand-50 hover:text-brand-600"
          >
            Safety Analysis (Conservative)
          </button>
          <button
            onClick={() =>
              setConfig({
                ...config,
                temperature: 0.3,
                topP: 0.95,
                frequencyPenalty: 0,
                presencePenalty: 0,
              })
            }
            className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-all hover:border-brand-500 hover:bg-brand-50 hover:text-brand-600"
          >
            Balanced (Default)
          </button>
          <button
            onClick={() =>
              setConfig({
                ...config,
                temperature: 0.7,
                topP: 1.0,
                frequencyPenalty: 0.3,
                presencePenalty: 0.3,
              })
            }
            className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-all hover:border-brand-500 hover:bg-brand-50 hover:text-brand-600"
          >
            Creative Brainstorming
          </button>
        </div>
      </section>

      {/* Save Button */}
      <button
        onClick={handleSave}
        className="flex items-center gap-2 rounded-xl gradient-brand px-6 py-3 text-sm font-semibold text-white shadow-md shadow-brand-500/20 transition-all hover:shadow-lg hover:shadow-brand-500/30"
      >
        <Save size={16} />
        {saved ? "Saved!" : "Save Changes"}
      </button>
    </div>
  );
}
