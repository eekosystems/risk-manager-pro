import { useState } from "react";
import { Database, Info, Save } from "lucide-react";

interface RagConfig {
  chunkSize: number;
  chunkOverlap: number;
  topK: number;
  scoreThreshold: number;
  searchType: "hybrid" | "vector" | "keyword";
  embeddingModel: string;
  rerankEnabled: boolean;
  maxContextTokens: number;
}

const DEFAULT_CONFIG: RagConfig = {
  chunkSize: 512,
  chunkOverlap: 50,
  topK: 5,
  scoreThreshold: 0.7,
  searchType: "hybrid",
  embeddingModel: "text-embedding-3-small",
  rerankEnabled: true,
  maxContextTokens: 4096,
};

export function RagSettingsTab() {
  const [config, setConfig] = useState<RagConfig>(DEFAULT_CONFIG);
  const [saved, setSaved] = useState(false);

  function handleSave() {
    setSaved(true);
    setTimeout(() => setSaved(false), 2000);
  }

  function updateConfig<K extends keyof RagConfig>(key: K, value: RagConfig[K]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  return (
    <div className="max-w-2xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">RAG Pipeline Settings</h2>
        <p className="text-sm text-slate-500">
          Configure how documents are processed, chunked, and retrieved for AI context.
        </p>
      </div>

      {/* Search Configuration */}
      <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-6">
        <div className="mb-5 flex items-center gap-2">
          <Database size={18} className="text-brand-500" />
          <h3 className="text-sm font-bold text-slate-800">Search Configuration</h3>
        </div>

        <div className="space-y-5">
          {/* Search Type */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Search Type
            </label>
            <div className="flex gap-2">
              {(["hybrid", "vector", "keyword"] as const).map((type) => (
                <button
                  key={type}
                  onClick={() => updateConfig("searchType", type)}
                  className={`rounded-xl px-4 py-2 text-sm font-medium transition-all ${
                    config.searchType === type
                      ? "gradient-brand text-white shadow-md shadow-brand-500/20"
                      : "border border-gray-200 bg-white text-gray-600 hover:bg-gray-50"
                  }`}
                >
                  {type.charAt(0).toUpperCase() + type.slice(1)}
                </button>
              ))}
            </div>
            <p className="mt-1.5 flex items-center gap-1 text-[12px] text-slate-400">
              <Info size={11} />
              Hybrid combines keyword + vector search for best results
            </p>
          </div>

          {/* Top K Results */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Top K Results
            </label>
            <input
              type="range"
              min={1}
              max={20}
              value={config.topK}
              onChange={(e) => updateConfig("topK", Number(e.target.value))}
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>1</span>
              <span className="font-semibold text-brand-500">{config.topK} documents</span>
              <span>20</span>
            </div>
          </div>

          {/* Score Threshold */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Relevance Score Threshold
            </label>
            <input
              type="range"
              min={0}
              max={100}
              value={config.scoreThreshold * 100}
              onChange={(e) =>
                updateConfig("scoreThreshold", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>0%</span>
              <span className="font-semibold text-brand-500">
                {Math.round(config.scoreThreshold * 100)}%
              </span>
              <span>100%</span>
            </div>
          </div>

          {/* Max Context Tokens */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Max Context Tokens
            </label>
            <input
              type="number"
              value={config.maxContextTokens}
              onChange={(e) =>
                updateConfig("maxContextTokens", Number(e.target.value))
              }
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
            <p className="mt-1.5 text-[12px] text-slate-400">
              Maximum number of tokens to include from retrieved documents
            </p>
          </div>
        </div>
      </section>

      {/* Document Processing */}
      <section className="mb-8 rounded-2xl border border-gray-200 bg-white p-6">
        <h3 className="mb-5 text-sm font-bold text-slate-800">Document Processing</h3>

        <div className="space-y-5">
          {/* Chunk Size */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Chunk Size (tokens)
            </label>
            <input
              type="number"
              value={config.chunkSize}
              onChange={(e) => updateConfig("chunkSize", Number(e.target.value))}
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          {/* Chunk Overlap */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Chunk Overlap (tokens)
            </label>
            <input
              type="number"
              value={config.chunkOverlap}
              onChange={(e) =>
                updateConfig("chunkOverlap", Number(e.target.value))
              }
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          {/* Embedding Model */}
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Embedding Model
            </label>
            <select
              value={config.embeddingModel}
              onChange={(e) => updateConfig("embeddingModel", e.target.value)}
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="text-embedding-3-small">text-embedding-3-small (1536 dims)</option>
              <option value="text-embedding-3-large">text-embedding-3-large (3072 dims)</option>
              <option value="text-embedding-ada-002">text-embedding-ada-002 (legacy)</option>
            </select>
          </div>

          {/* Reranking */}
          <div className="flex items-center justify-between">
            <div>
              <span className="text-[13px] font-semibold text-slate-700">
                Enable Reranking
              </span>
              <p className="text-[12px] text-slate-400">
                Rerank retrieved documents for better relevance
              </p>
            </div>
            <button
              onClick={() => updateConfig("rerankEnabled", !config.rerankEnabled)}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                config.rerankEnabled ? "bg-brand-500" : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  config.rerankEnabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
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
