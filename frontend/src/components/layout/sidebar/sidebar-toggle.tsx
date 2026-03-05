import { clsx } from "clsx";
import { ChevronRight } from "lucide-react";

interface SidebarToggleProps {
  isOpen: boolean;
  onToggle: () => void;
}

export function SidebarToggle({ isOpen, onToggle }: SidebarToggleProps) {
  return (
    <button
      onClick={onToggle}
      aria-label={isOpen ? "Collapse sidebar" : "Expand sidebar"}
      className={clsx(
        "fixed top-1/2 z-30 -translate-y-1/2 rounded-r-lg border border-l-0 border-gray-200 bg-white p-1.5 text-gray-400 shadow-sm transition-all hover:bg-brand-50 hover:text-brand-500",
        isOpen ? "left-[299px]" : "left-0",
      )}
    >
      <ChevronRight
        size={16}
        className={clsx("transition-transform", isOpen && "rotate-180")}
      />
    </button>
  );
}
