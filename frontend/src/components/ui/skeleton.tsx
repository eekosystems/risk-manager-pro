import { clsx } from "clsx";

interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className }: SkeletonProps) {
  return (
    <div
      className={clsx("animate-shimmer rounded-lg bg-gray-200", className)}
      aria-hidden="true"
    />
  );
}
