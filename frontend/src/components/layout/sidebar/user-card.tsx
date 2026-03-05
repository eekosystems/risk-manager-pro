import { LogOut, Shield } from "lucide-react";

import { useAuth } from "@/hooks/use-auth";

export function UserCard() {
  const { userName, logout } = useAuth();

  return (
    <div className="border-t border-gray-100 px-4 py-3">
      <div className="flex items-center gap-3">
        <div className="relative">
          <div className="flex h-9 w-9 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-600">
            {userName?.charAt(0)?.toUpperCase() ?? "U"}
          </div>
          <div className="absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white bg-green-500" />
        </div>
        <div className="flex flex-1 flex-col overflow-hidden">
          <span className="truncate text-sm font-semibold text-gray-800">
            {userName ?? "User"}
          </span>
          <div className="flex items-center gap-1">
            <Shield size={10} className="text-brand-500" />
            <span className="truncate text-[11px] text-gray-400">
              Safety Manager
            </span>
          </div>
        </div>
        <button
          onClick={() => void logout()}
          className="rounded-lg p-1.5 text-gray-400 hover:bg-gray-100 hover:text-gray-600"
          aria-label="Sign out"
        >
          <LogOut size={16} />
        </button>
      </div>
    </div>
  );
}
