import { useState } from "react";
import {
  Crown,
  Mail,
  MoreVertical,
  Plus,
  Search,
  Shield,
  Eye,
  Trash2,
  UserPlus,
  X,
} from "lucide-react";

import type { MembershipRole } from "@/types/api";

interface TeamMember {
  id: string;
  displayName: string;
  email: string;
  role: MembershipRole;
  isActive: boolean;
  lastLogin: string | null;
  addedAt: string;
}

const DEMO_MEMBERS: TeamMember[] = [
  {
    id: "1",
    displayName: "Thomas Unise",
    email: "thomasunise@gmail.com",
    role: "org_admin",
    isActive: true,
    lastLogin: "2026-03-09T05:00:00Z",
    addedAt: "2026-02-01T10:00:00Z",
  },
  {
    id: "2",
    displayName: "Sarah Mitchell",
    email: "s.mitchell@faithgroup.com",
    role: "analyst",
    isActive: true,
    lastLogin: "2026-03-08T14:30:00Z",
    addedAt: "2026-02-15T09:00:00Z",
  },
  {
    id: "3",
    displayName: "James Rivera",
    email: "j.rivera@faithgroup.com",
    role: "analyst",
    isActive: true,
    lastLogin: "2026-03-07T11:45:00Z",
    addedAt: "2026-02-20T08:00:00Z",
  },
  {
    id: "4",
    displayName: "Emily Chen",
    email: "e.chen@faithgroup.com",
    role: "viewer",
    isActive: true,
    lastLogin: "2026-03-05T16:20:00Z",
    addedAt: "2026-03-01T10:00:00Z",
  },
  {
    id: "5",
    displayName: "Mike Johnson",
    email: "m.johnson@faithgroup.com",
    role: "viewer",
    isActive: false,
    lastLogin: "2026-02-20T09:00:00Z",
    addedAt: "2026-02-10T10:00:00Z",
  },
];

const ROLE_CONFIG: Record<
  MembershipRole,
  { label: string; icon: typeof Shield; className: string; bgClassName: string; description: string }
> = {
  org_admin: {
    label: "Admin",
    icon: Crown,
    className: "text-amber-600",
    bgClassName: "bg-amber-50 text-amber-700 border-amber-200",
    description: "Full access to all settings, users, and data",
  },
  analyst: {
    label: "Analyst",
    icon: Shield,
    className: "text-brand-600",
    bgClassName: "bg-brand-50 text-brand-700 border-brand-200",
    description: "Can run assessments, upload documents, view reports",
  },
  viewer: {
    label: "Viewer",
    icon: Eye,
    className: "text-slate-600",
    bgClassName: "bg-slate-50 text-slate-700 border-slate-200",
    description: "Read-only access to reports and assessments",
  },
};

function formatDate(iso: string | null): string {
  if (!iso) return "Never";
  return new Date(iso).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function UsersRolesTab() {
  const [members, setMembers] = useState<TeamMember[]>(DEMO_MEMBERS);
  const [searchQuery, setSearchQuery] = useState("");
  const [showInvite, setShowInvite] = useState(false);
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<MembershipRole>("viewer");
  const [menuOpen, setMenuOpen] = useState<string | null>(null);
  const [deleteConfirm, setDeleteConfirm] = useState<string | null>(null);

  const filteredMembers = members.filter(
    (m) =>
      m.displayName.toLowerCase().includes(searchQuery.toLowerCase()) ||
      m.email.toLowerCase().includes(searchQuery.toLowerCase()),
  );

  function handleInvite() {
    if (!inviteEmail.trim()) return;
    const newMember: TeamMember = {
      id: String(Date.now()),
      displayName: inviteEmail.split("@")[0] ?? "New User",
      email: inviteEmail,
      role: inviteRole,
      isActive: false,
      lastLogin: null,
      addedAt: new Date().toISOString(),
    };
    setMembers((prev) => [...prev, newMember]);
    setInviteEmail("");
    setShowInvite(false);
  }

  function handleRoleChange(id: string, newRole: MembershipRole) {
    setMembers((prev) =>
      prev.map((m) => (m.id === id ? { ...m, role: newRole } : m)),
    );
    setMenuOpen(null);
  }

  function handleRemove(id: string) {
    if (deleteConfirm === id) {
      setMembers((prev) => prev.filter((m) => m.id !== id));
      setDeleteConfirm(null);
      setMenuOpen(null);
    } else {
      setDeleteConfirm(id);
      setTimeout(() => setDeleteConfirm(null), 3000);
    }
  }

  function handleToggleActive(id: string) {
    setMembers((prev) =>
      prev.map((m) => (m.id === id ? { ...m, isActive: !m.isActive } : m)),
    );
    setMenuOpen(null);
  }

  return (
    <div className="max-w-3xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Users & Roles</h2>
        <p className="text-sm text-slate-500">
          Manage team members and their access levels.
        </p>
      </div>

      {/* Role breakdown */}
      <div className="mb-6 grid grid-cols-3 gap-4">
        {(Object.keys(ROLE_CONFIG) as MembershipRole[]).map((role) => {
          const config = ROLE_CONFIG[role];
          const Icon = config.icon;
          const count = members.filter(
            (m) => m.role === role && m.isActive,
          ).length;
          return (
            <div
              key={role}
              className="rounded-2xl border border-gray-200 bg-white p-4"
            >
              <div className="mb-1 flex items-center gap-2">
                <Icon size={16} className={config.className} />
                <span className="text-sm font-semibold text-slate-700">
                  {config.label}s
                </span>
              </div>
              <div className="text-2xl font-bold text-brand-500">{count}</div>
              <div className="text-[11px] text-slate-400">
                {config.description}
              </div>
            </div>
          );
        })}
      </div>

      {/* Actions */}
      <div className="mb-4 flex items-center gap-3">
        <button
          onClick={() => setShowInvite(!showInvite)}
          className="flex items-center gap-2 rounded-xl gradient-brand px-4 py-2.5 text-sm font-semibold text-white shadow-md shadow-brand-500/20 transition-all hover:shadow-lg hover:shadow-brand-500/30"
        >
          <UserPlus size={16} />
          Invite Member
        </button>
        <div className="relative flex-1">
          <Search
            size={16}
            className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
          />
          <input
            type="text"
            placeholder="Search by name or email..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            className="w-full rounded-xl border border-gray-200 py-2.5 pl-10 pr-4 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
        </div>
      </div>

      {/* Invite form */}
      {showInvite && (
        <div className="mb-4 rounded-2xl border border-brand-200 bg-brand-50 p-5">
          <div className="mb-3 flex items-center justify-between">
            <h3 className="text-sm font-bold text-slate-800">Invite New Member</h3>
            <button
              onClick={() => setShowInvite(false)}
              className="rounded-lg p-1 text-gray-400 hover:bg-white hover:text-gray-600"
            >
              <X size={16} />
            </button>
          </div>
          <div className="flex gap-3">
            <div className="relative flex-1">
              <Mail
                size={16}
                className="absolute left-3 top-1/2 -translate-y-1/2 text-gray-400"
              />
              <input
                type="email"
                placeholder="email@faithgroup.com"
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                className="w-full rounded-xl border border-gray-200 bg-white py-2.5 pl-10 pr-4 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
                onKeyDown={(e) => {
                  if (e.key === "Enter") handleInvite();
                }}
              />
            </div>
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as MembershipRole)}
              className="rounded-xl border border-gray-200 bg-white px-4 py-2.5 text-sm text-slate-600 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
            >
              <option value="viewer">Viewer</option>
              <option value="analyst">Analyst</option>
              <option value="org_admin">Admin</option>
            </select>
            <button
              onClick={handleInvite}
              className="flex items-center gap-1.5 rounded-xl gradient-brand px-5 py-2.5 text-sm font-semibold text-white"
            >
              <Plus size={16} />
              Send Invite
            </button>
          </div>
        </div>
      )}

      {/* Members list */}
      <div className="rounded-2xl border border-gray-200 bg-white">
        {filteredMembers.map((member, index) => {
          const roleConfig = ROLE_CONFIG[member.role];
          const RoleIcon = roleConfig.icon;
          return (
            <div
              key={member.id}
              className={`flex items-center gap-4 px-5 py-4 ${
                index < filteredMembers.length - 1
                  ? "border-b border-gray-100"
                  : ""
              }`}
            >
              {/* Avatar */}
              <div className="relative">
                <div className="flex h-10 w-10 items-center justify-center rounded-full bg-brand-100 text-sm font-bold text-brand-600">
                  {member.displayName.charAt(0).toUpperCase()}
                </div>
                <div
                  className={`absolute -bottom-0.5 -right-0.5 h-3 w-3 rounded-full border-2 border-white ${
                    member.isActive ? "bg-green-500" : "bg-gray-300"
                  }`}
                />
              </div>

              {/* Info */}
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <span className="truncate text-sm font-semibold text-slate-800">
                    {member.displayName}
                  </span>
                  {!member.isActive && (
                    <span className="rounded-full border border-gray-200 bg-gray-50 px-2 py-0.5 text-[10px] font-bold text-gray-500">
                      Inactive
                    </span>
                  )}
                </div>
                <span className="text-[12px] text-slate-400">
                  {member.email}
                </span>
              </div>

              {/* Role badge */}
              <span
                className={`flex items-center gap-1.5 rounded-full border px-3 py-1 text-[11px] font-bold ${roleConfig.bgClassName}`}
              >
                <RoleIcon size={12} />
                {roleConfig.label}
              </span>

              {/* Last login */}
              <div className="hidden text-right sm:block">
                <div className="text-[11px] text-slate-400">Last login</div>
                <div className="text-[12px] font-medium text-slate-600">
                  {formatDate(member.lastLogin)}
                </div>
              </div>

              {/* Actions */}
              <div className="relative">
                <button
                  onClick={() =>
                    setMenuOpen(menuOpen === member.id ? null : member.id)
                  }
                  className="rounded-lg p-2 text-gray-300 transition-colors hover:bg-gray-50 hover:text-gray-500"
                >
                  <MoreVertical size={16} />
                </button>

                {menuOpen === member.id && (
                  <div className="absolute right-0 top-full z-10 mt-1 w-48 rounded-xl border border-gray-200 bg-white py-1 shadow-lg">
                    <div className="px-3 py-1.5 text-[11px] font-bold uppercase tracking-wider text-slate-400">
                      Change Role
                    </div>
                    {(Object.keys(ROLE_CONFIG) as MembershipRole[]).map(
                      (role) => (
                        <button
                          key={role}
                          onClick={() => handleRoleChange(member.id, role)}
                          className={`w-full px-3 py-2 text-left text-sm transition-colors hover:bg-gray-50 ${
                            member.role === role
                              ? "font-semibold text-brand-600"
                              : "text-slate-600"
                          }`}
                        >
                          {ROLE_CONFIG[role].label}
                          {member.role === role && " (current)"}
                        </button>
                      ),
                    )}
                    <div className="my-1 h-px bg-gray-100" />
                    <button
                      onClick={() => handleToggleActive(member.id)}
                      className="w-full px-3 py-2 text-left text-sm text-slate-600 transition-colors hover:bg-gray-50"
                    >
                      {member.isActive ? "Deactivate" : "Reactivate"}
                    </button>
                    <button
                      onClick={() => handleRemove(member.id)}
                      className={`w-full px-3 py-2 text-left text-sm transition-colors hover:bg-red-50 ${
                        deleteConfirm === member.id
                          ? "font-semibold text-red-600"
                          : "text-red-500"
                      }`}
                    >
                      <span className="flex items-center gap-2">
                        <Trash2 size={14} />
                        {deleteConfirm === member.id
                          ? "Click again to confirm"
                          : "Remove"}
                      </span>
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
