import { Search, Settings } from "lucide-react";

interface HeaderBarProps {
  onSettingsClick?: () => void;
}

export function HeaderBar({ onSettingsClick }: HeaderBarProps) {
  return (
    <div className="flex items-center justify-between border-b border-gray-200 bg-white px-8 py-4">
      <div className="flex flex-col">
        <h1 className="text-[22px] font-bold text-slate-900">
          Risk Manager Pro
        </h1>
        <p className="text-[13px] text-slate-500">
          AI-powered risk analysis using indexed Faith Group safety data
        </p>
      </div>

      <div className="flex items-center gap-3">
        <div className="flex items-center gap-2 rounded-xl border border-gray-200 bg-gray-50 px-4 py-2.5">
          <Search size={16} className="text-gray-400" />
          <span className="text-sm text-gray-400">Search conversations...</span>
          <kbd className="ml-4 rounded-md border border-gray-200 bg-white px-1.5 py-0.5 text-[11px] font-medium text-gray-400">
            ⌘K
          </kbd>
        </div>
        <button
          onClick={onSettingsClick}
          className="rounded-xl border border-gray-200 p-2.5 text-gray-400 transition-colors hover:bg-gray-50 hover:text-gray-600"
          aria-label="Settings"
        >
          <Settings size={18} />
        </button>
      </div>
    </div>
  );
}
