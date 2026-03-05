import { clsx } from "clsx";
import { Building2, ChevronDown } from "lucide-react";
import { useCallback, useRef, useState } from "react";

import { useClickOutside } from "@/hooks/use-click-outside";
import type { OrganizationSummary } from "@/types/api";

interface OrganizationSwitcherProps {
  activeOrganization: OrganizationSummary;
  organizations: OrganizationSummary[];
  onOrganizationSelect: (org: OrganizationSummary) => void;
}

export function OrganizationSwitcher({
  activeOrganization,
  organizations,
  onOrganizationSelect,
}: OrganizationSwitcherProps) {
  const [isOpen, setIsOpen] = useState(false);
  const dropdownRef = useRef<HTMLDivElement>(null);
  const showSwitcher = organizations.length > 1;

  const handleClose = useCallback(() => setIsOpen(false), []);
  useClickOutside(dropdownRef, isOpen, handleClose);

  return (
    <div className="border-b border-gray-100 px-3 py-2">
      <div className="relative" ref={dropdownRef}>
        <button
          onClick={() => showSwitcher && setIsOpen(!isOpen)}
          aria-expanded={isOpen}
          aria-haspopup="listbox"
          aria-label="Switch organization"
          className={clsx(
            "flex w-full items-center gap-2 rounded-lg px-3 py-2 text-left",
            showSwitcher
              ? "hover:bg-gray-50 cursor-pointer"
              : "cursor-default",
          )}
        >
          <Building2 size={16} className="shrink-0 text-brand-500" />
          <span className="flex-1 truncate text-sm font-medium text-gray-700">
            {activeOrganization.name}
          </span>
          {showSwitcher && (
            <ChevronDown
              size={14}
              className={clsx(
                "text-gray-400 transition-transform",
                isOpen && "rotate-180",
              )}
            />
          )}
        </button>

        {isOpen && showSwitcher && (
          <div
            role="listbox"
            aria-label="Organizations"
            className="absolute left-0 right-0 top-full z-20 mt-1 rounded-lg border border-gray-200 bg-white py-1 shadow-lg"
          >
            {organizations.map((org) => (
              <button
                key={org.id}
                role="option"
                aria-selected={org.id === activeOrganization.id}
                onClick={() => {
                  onOrganizationSelect(org);
                  setIsOpen(false);
                }}
                className={clsx(
                  "flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-gray-50",
                  org.id === activeOrganization.id
                    ? "font-semibold text-brand-600"
                    : "text-gray-700",
                )}
              >
                <Building2 size={14} className="shrink-0" />
                <span className="truncate">{org.name}</span>
                {org.is_platform && (
                  <span className="ml-auto text-[10px] font-medium text-brand-500">
                    Platform
                  </span>
                )}
              </button>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
