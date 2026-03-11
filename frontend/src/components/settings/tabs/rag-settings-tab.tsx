import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, Database, Info, Loader2, RefreshCw, Save } from "lucide-react";

import {
  getSettingsByCategory,
  updateRagSettings,
  type RagSettings,
} from "@/api/settings";

const DEFAULT_CONFIG: RagSettings = {
  chunk_size: 512,
  chunk_overlap: 50,
  top_k: 5,
  score_threshold: 0.7,
  search_type: "hybrid",
  embedding_model: "text-embedding-3-small",
  rerank_enabled: true,
  max_context_tokens: 4096,
};

export function RagSettingsTab() {
  const queryClient = useQueryClient();
  const [config, setConfig] = useState<RagSettings>(DEFAULT_CONFIG);

  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["settings", "rag"],
    queryFn: () => getSettingsByCategory("rag"),
  });

  useEffect(() => {
    if (data?.settings) {
      setConfig(data.settings as unknown as RagSettings);
    }
  }, [data]);

  const mutation = useMutation({
    mutationFn: updateRagSettings,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["settings", "rag"] });
    },
  });

  function updateConfig<K extends keyof RagSettings>(key: K, value: RagSettings[K]) {
    setConfig((prev) => ({ ...prev, [key]: value }));
  }

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-20">
        <Loader2 size={24} className="animate-spin text-brand-500" />
      </div>
    );
  }

  if (isError) {
    return (
      <div className="flex flex-col items-center justify-center py-20 text-center">
        <AlertTriangle size={32} className="mb-3 text-red-400" />
        <p className="text-sm font-semibold text-slate-700">Failed to load RAG settings</p>
        <p className="mb-4 text-[13px] text-slate-400">The server may be unavailable. Check the browser console for details.</p>
        <button
          onClick={() => void refetch()}
          className="flex items-center gap-2 rounded-xl border border-gray-200 px-4 py-2 text-sm font-medium text-gray-600 transition-colors hover:bg-gray-50"
        >
          <RefreshCw size={14} />
          Retry
        </button>
      </div>
    );
  }

  return (
    <div className="max-w-5xl">
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
                  onClick={() => updateConfig("search_type", type)}
                  className={`rounded-xl px-4 py-2 text-sm font-medium transition-all ${
                    config.search_type === type
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
              value={config.top_k}
              onChange={(e) => updateConfig("top_k", Number(e.target.value))}
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>1</span>
              <span className="font-semibold text-brand-500">{config.top_k} documents</span>
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
              value={config.score_threshold * 100}
              onChange={(e) =>
                updateConfig("score_threshold", Number(e.target.value) / 100)
              }
              className="w-full accent-brand-500"
            />
            <div className="flex justify-between text-[12px] text-slate-400">
              <span>0%</span>
              <span className="font-semibold text-brand-500">
                {Math.round(config.score_threshold * 100)}%
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
              value={config.max_context_tokens}
              onChange={(e) =>
                updateConfig("max_context_tokens", Number(e.target.value))
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
          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Chunk Size (tokens)
            </label>
            <input
              type="number"
              value={config.chunk_size}
              onChange={(e) => updateConfig("chunk_size", Number(e.target.value))}
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Chunk Overlap (tokens)
            </label>
            <input
              type="number"
              value={config.chunk_overlap}
              onChange={(e) =>
                updateConfig("chunk_overlap", Number(e.target.value))
              }
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div>
            <label className="mb-1.5 block text-[13px] font-semibold text-slate-700">
              Embedding Model
            </label>
            <select
              value={config.embedding_model}
              onChange={(e) => updateConfig("embedding_model", e.target.value)}
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="text-embedding-3-small">text-embedding-3-small (1536 dims)</option>
              <option value="text-embedding-3-large">text-embedding-3-large (3072 dims)</option>
              <option value="text-embedding-ada-002">text-embedding-ada-002 (legacy)</option>
            </select>
          </div>

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
              onClick={() => updateConfig("rerank_enabled", !config.rerank_enabled)}
              className={`relative h-6 w-11 rounded-full transition-colors ${
                config.rerank_enabled ? "bg-brand-500" : "bg-gray-300"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 h-5 w-5 rounded-full bg-white shadow transition-transform ${
                  config.rerank_enabled ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
          </div>
        </div>
      </section>

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
