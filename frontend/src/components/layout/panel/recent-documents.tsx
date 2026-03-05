import { FileText, Upload } from "lucide-react";

import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocuments } from "@/hooks/use-documents";

export function RecentDocuments() {
  const {
    data: documents = [],
    isLoading,
    isError,
  } = useDocuments();

  return (
    <>
      <h3 className="mb-3 flex items-center gap-1.5 text-[11px] font-bold uppercase tracking-wider text-gray-400">
        <FileText size={12} />
        Recent Documents
      </h3>
      <div className="mb-6 flex flex-col gap-1.5">
        {isLoading && (
          <div className="flex flex-col gap-2 px-2">
            {Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="flex items-center gap-2">
                <Skeleton className="h-4 w-4 shrink-0" />
                <Skeleton className="h-4 flex-1" />
                <Skeleton className="h-3 w-12" />
              </div>
            ))}
          </div>
        )}

        {isError && (
          <p className="px-2 text-xs text-red-500">
            Failed to load documents
          </p>
        )}

        {!isLoading && !isError && documents.length === 0 && (
          <EmptyState
            icon={Upload}
            title="No documents yet"
            description="Upload safety documents to power the AI knowledge base"
          />
        )}

        {!isLoading &&
          !isError &&
          documents.slice(0, 5).map((doc) => (
            <div
              key={doc.id}
              className="flex items-center gap-2.5 rounded-lg px-2 py-1.5 hover:bg-gray-50"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-brand-50">
                <FileText size={14} className="text-brand-500" />
              </div>
              <div className="flex flex-1 flex-col overflow-hidden">
                <span className="truncate text-[12px] font-medium text-gray-700">
                  {doc.filename}
                </span>
                <span className="text-[11px] text-gray-400">
                  {doc.status === "indexed" ? "Indexed" : doc.status}
                </span>
              </div>
            </div>
          ))}
      </div>
    </>
  );
}
