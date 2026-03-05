import { useQuery } from "@tanstack/react-query";
import { clsx } from "clsx";
import { Database } from "lucide-react";

import { getHealthStatus, type HealthStatus } from "@/api/health";
import { useDocuments } from "@/hooks/use-documents";

export function AiStatusCard() {
  const { data: health } = useQuery<HealthStatus>({
    queryKey: ["health"],
    queryFn: getHealthStatus,
    refetchInterval: 30_000,
  });
  const { data: documents = [] } = useDocuments();

  const isOnline = health?.status === "healthy";

  return (
    <>
      <h3 className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
        <Database size={12} />
        AI Status
      </h3>
      <div className="rounded-xl border border-gray-200 bg-gray-50 p-3" role="status">
        <div className="mb-2 flex items-center gap-2">
          <div
            className={clsx(
              "h-2 w-2 rounded-full",
              isOnline ? "bg-green-500" : "bg-yellow-500",
            )}
          />
          <span className="text-sm font-medium text-gray-700">
            {isOnline ? "System Online" : health ? "Degraded" : "Checking..."}
          </span>
        </div>
        <div className="space-y-1 text-[11px] text-gray-500">
          <p>Model: GPT-4o (Azure)</p>
          <p>
            Database:{" "}
            {health?.checks?.database === "ok" ? "Connected" : "Unknown"}
          </p>
          <p>Documents: {documents.length} loaded</p>
        </div>
      </div>
    </>
  );
}
