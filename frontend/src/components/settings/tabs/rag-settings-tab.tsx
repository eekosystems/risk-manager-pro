import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Database, Info, Loader2, Save } from "lucide-react";

import {
  getSettingsByCategory,
  updateRagSettings,
  type RagSettings,
} from "@/api/settings";
import { SettingsSection } from "@/components/settings/settings-section";
import { InfoTooltip } from "@/components/ui/info-tooltip";

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

  const { data, isLoading } = useQuery({
    queryKey: ["settings", "rag"],
    queryFn: () => getSettingsByCategory<RagSettings>("rag"),
    retry: false,
  });

  useEffect(() => {
    if (data?.settings) {
      setConfig(data.settings);
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


  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">RAG Pipeline Settings</h2>
        <p className="text-sm text-slate-500">
          Configure how documents are processed, chunked, and retrieved for AI context.
        </p>
      </div>

      {/* Search Configuration */}
      <div className="mb-8"><SettingsSection>
        <div className="mb-5 flex items-center gap-2">
          <Database size={18} className="text-brand-500" />
          <h3 className="text-sm font-bold text-slate-800">Search Configuration</h3>
        </div>

        <div className="space-y-5">
          {/* Search Type */}
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
              Search Type
              <InfoTooltip
                label="About search type"
                content={
                  <>
                    Controls how the system finds documents to answer your
                    questions. <strong>Hybrid</strong> blends keyword matching
                    (good for proper nouns and exact terms) with vector
                    similarity (good for paraphrased concepts).{" "}
                    <strong>Vector</strong> only relies on semantic meaning;{" "}
                    <strong>Keyword</strong> only on literal word matches.
                    Hybrid is recommended for safety documents where both
                    regulatory citations and conceptual queries appear.
                  </>
                }
              />
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
            <label className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
              Top K Results
              <InfoTooltip
                label="About top K"
                content={
                  <>
                    How many of the most relevant document passages the AI
                    sees when answering. Higher values give the model more
                    context but can dilute focus and increase cost. 5–8 is a
                    good range for most safety analysis queries.
                  </>
                }
              />
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
            <label className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
              Relevance Score Threshold
              <InfoTooltip
                label="About relevance threshold"
                content={
                  <>
                    Minimum similarity score a passage must clear to be passed
                    to the AI. Higher values produce stricter, more focused
                    answers but may return fewer results. Lower values cast a
                    wider net at the cost of noise. 70% is a balanced default.
                  </>
                }
              />
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
            <label className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
              Max Context Tokens
              <InfoTooltip
                label="About max context tokens"
                content={
                  <>
                    Upper limit on how much retrieved document text the AI
                    can consider for one answer. A "token" is roughly ¾ of a
                    word. Higher = more context but slower and more expensive.
                    The model also has a hard ceiling (e.g. 128K for GPT-4o).
                  </>
                }
              />
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
      </SettingsSection></div>

      {/* Document Processing */}
      <div className="mb-8"><SettingsSection>
        <h3 className="mb-5 text-sm font-bold text-slate-800">Document Processing</h3>

        <div className="space-y-5">
          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
              Chunk Size (tokens)
              <InfoTooltip
                label="About chunk size"
                content={
                  <>
                    Documents are split into smaller passages ("chunks")
                    before being indexed. Larger chunks preserve more
                    surrounding context per passage; smaller chunks let
                    retrieval pinpoint a specific paragraph. 512 tokens
                    (~380 words) is a good default for SMS / regulatory text.
                  </>
                }
              />
            </label>
            <input
              type="number"
              value={config.chunk_size}
              onChange={(e) => updateConfig("chunk_size", Number(e.target.value))}
              className="w-full rounded-xl border border-gray-200 px-4 py-2.5 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            />
          </div>

          <div>
            <label className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
              Chunk Overlap (tokens)
              <InfoTooltip
                label="About chunk overlap"
                content={
                  <>
                    How many tokens at the end of one chunk are repeated at
                    the start of the next. Overlap prevents a sentence or
                    hazard description that sits on a chunk boundary from
                    being lost. ~10% of chunk size (e.g. 50 for 512) is
                    typical.
                  </>
                }
              />
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
            <label className="mb-1.5 flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
              Embedding Model
              <InfoTooltip
                label="About embedding model"
                content={
                  <>
                    The model that turns text into the numeric vectors used
                    for similarity search. Larger models capture more nuance
                    but cost more and produce bigger indexes. Changing this
                    requires re-indexing every existing document — only
                    switch when migrating off a legacy model.
                  </>
                }
              />
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
              <span className="flex items-center gap-1.5 text-[13px] font-semibold text-slate-700">
                Enable Reranking
                <InfoTooltip
                  label="About reranking"
                  content={
                    <>
                      A second-pass scoring step that re-orders the retrieved
                      passages by relevance to the actual question, using a
                      more expensive but more accurate model. Improves answer
                      quality at the cost of slightly higher latency per
                      query. Recommended on for safety-critical analysis.
                    </>
                  }
                />
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
