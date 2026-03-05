import { Skeleton } from "./skeleton";

interface ConversationSkeletonProps {
  count?: number;
}

export function ConversationSkeleton({ count = 5 }: ConversationSkeletonProps) {
  return (
    <div className="flex flex-col gap-1">
      {Array.from({ length: count }).map((_, i) => (
        <div key={i} className="rounded-lg px-3 py-2">
          <Skeleton className="mb-1.5 h-4 w-3/4" />
          <Skeleton className="h-3 w-1/3" />
        </div>
      ))}
    </div>
  );
}
