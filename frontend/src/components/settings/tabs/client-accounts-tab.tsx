import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  Building2,
  Check,
  FolderTree,
  Loader2,
  Plus,
  ShieldCheck,
  Trash2,
  UserPlus,
  X,
} from "lucide-react";
import { useState } from "react";

import {
  addMember,
  createOrganization,
  getFolderScopes,
  getOrganizationMembers,
  getOrganizations,
  removeMember,
  setFolderScopes,
} from "@/api/organizations";
import { setPlatformAdmin } from "@/api/users";
import { useUserRole } from "@/hooks/use-user-role";
import type {
  MembershipRole,
  OrganizationMember,
  OrganizationSummary,
} from "@/types/api";

const ROLE_LABELS: Record<MembershipRole, string> = {
  org_admin: "Account admin",
  analyst: "Analyst",
  viewer: "Viewer",
};

const ROLE_ORDER: MembershipRole[] = ["org_admin", "analyst", "viewer"];

function slugify(name: string): string {
  return name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 100);
}

export function ClientAccountsTab() {
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [creating, setCreating] = useState(false);

  const { data: accounts = [], isLoading } = useQuery({
    queryKey: ["organizations"],
    queryFn: getOrganizations,
    retry: false,
  });

  const selected = accounts.find((a) => a.id === selectedId) ?? null;

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-16">
        <Loader2 size={22} className="animate-spin text-brand-500" />
      </div>
    );
  }

  return (
    <div className="max-w-5xl">
      <div className="mb-6">
        <h2 className="text-lg font-bold text-slate-900">Client Accounts</h2>
        <p className="text-sm text-slate-500">
          Each account is an isolated environment. Its users see only the
          SharePoint folders you grant it, plus whatever they upload themselves.
        </p>
      </div>

      <div className="mb-4 flex items-center justify-between">
        <span className="text-[12px] text-slate-400">
          {accounts.length} {accounts.length === 1 ? "account" : "accounts"}
        </span>
        <button
          onClick={() => setCreating(true)}
          className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white transition-colors hover:bg-brand-700"
        >
          <Plus size={15} />
          Add Account
        </button>
      </div>

      {accounts.length === 0 ? (
        <div className="rounded-2xl border border-gray-200 bg-white p-10 text-center text-sm text-slate-400">
          No accounts yet. Add one to give a client an isolated environment.
        </div>
      ) : (
        <div className="space-y-2">
          {accounts.map((account) => (
            <AccountRow
              key={account.id}
              account={account}
              onManage={() => setSelectedId(account.id)}
            />
          ))}
        </div>
      )}

      {creating && <CreateAccountModal onClose={() => setCreating(false)} />}
      {selected && (
        <ManageAccountModal
          account={selected}
          onClose={() => setSelectedId(null)}
        />
      )}
    </div>
  );
}

function AccountRow({
  account,
  onManage,
}: {
  account: OrganizationSummary;
  onManage: () => void;
}) {
  const { data: scope } = useQuery({
    queryKey: ["folder-scopes", account.id],
    queryFn: () => getFolderScopes(account.id),
    retry: false,
  });

  return (
    <div className="flex items-center gap-3 rounded-2xl border border-gray-200 bg-white p-4">
      <Building2 size={18} className="shrink-0 text-brand-500" />
      <div className="min-w-0 flex-1">
        <div className="flex items-center gap-2">
          <span className="text-sm font-semibold text-slate-800">
            {account.name}
          </span>
          {account.is_platform && (
            <span className="rounded-full bg-accent-50 px-2 py-0.5 text-[10px] font-bold text-accent-700">
              Platform
            </span>
          )}
          {account.status !== "active" && (
            <span className="rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-bold text-slate-500">
              {account.status}
            </span>
          )}
        </div>
        <div className="mt-0.5 flex items-center gap-1.5 text-[11px] text-slate-400">
          <FolderTree size={11} className="shrink-0" />
          {scope?.unrestricted ? (
            <span>Entire library</span>
          ) : scope && scope.folder_paths.length > 0 ? (
            <span className="truncate">
              {scope.folder_paths.map((p) => p.split("/").pop()).join(", ")}
            </span>
          ) : (
            <span className="font-semibold text-amber-600">
              No folders assigned — imports nothing
            </span>
          )}
        </div>
      </div>
      <button
        onClick={onManage}
        className="shrink-0 rounded-lg border border-gray-200 px-3 py-1.5 text-[12px] font-semibold text-slate-600 transition-colors hover:bg-gray-50"
      >
        Manage
      </button>
    </div>
  );
}

// --- Create ---

function CreateAccountModal({ onClose }: { onClose: () => void }) {
  const queryClient = useQueryClient();
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [slugEdited, setSlugEdited] = useState(false);

  const mutation = useMutation({
    mutationFn: createOrganization,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["organizations"] });
      onClose();
    },
  });

  const effectiveSlug = slugEdited ? slug : slugify(name);

  return (
    <ModalShell title="Add client account" onClose={onClose}>
      <p className="mb-4 rounded-xl border border-brand-100 bg-brand-50/50 px-3 py-2 text-[11px] leading-snug text-brand-800">
        Creates an isolated environment. After it exists, assign its SharePoint
        folders and add its users from Manage — until a folder is assigned the
        account imports nothing.
      </p>

      <label
        htmlFor="account-name"
        className="mb-1.5 block text-[12px] font-semibold text-slate-700"
      >
        Account name
      </label>
      <input
        id="account-name"
        autoFocus
        value={name}
        maxLength={255}
        onChange={(e) => setName(e.target.value)}
        placeholder="Seattle-Tacoma International Airport"
        className="mb-4 w-full rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
      />

      <label
        htmlFor="account-slug"
        className="mb-1.5 block text-[12px] font-semibold text-slate-700"
      >
        Identifier
      </label>
      <input
        id="account-slug"
        value={effectiveSlug}
        maxLength={100}
        onChange={(e) => {
          setSlugEdited(true);
          setSlug(slugify(e.target.value));
        }}
        placeholder="seattle-tacoma"
        className="w-full rounded-xl border border-gray-200 px-3 py-2 font-mono text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
      />
      <p className="mt-1 text-[11px] text-slate-400">
        Lowercase letters, numbers and hyphens. Cannot be changed later.
      </p>

      {mutation.isError && (
        <div className="mt-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          The account could not be created. The identifier may already be taken.
        </div>
      )}

      <ModalActions
        onClose={onClose}
        onSubmit={() =>
          mutation.mutate({ name: name.trim(), slug: effectiveSlug })
        }
        submitLabel="Create account"
        disabled={!name.trim() || !effectiveSlug}
        pending={mutation.isPending}
      />
    </ModalShell>
  );
}

// --- Manage ---

function ManageAccountModal({
  account,
  onClose,
}: {
  account: OrganizationSummary;
  onClose: () => void;
}) {
  return (
    <ModalShell title={account.name} onClose={onClose} wide>
      <FolderScopeSection account={account} />
      <div className="my-5 border-t border-gray-100" />
      <MembersSection account={account} />
    </ModalShell>
  );
}

function FolderScopeSection({ account }: { account: OrganizationSummary }) {
  const queryClient = useQueryClient();
  const [draft, setDraft] = useState<string | null>(null);
  const [newPath, setNewPath] = useState("");

  const { data: scope, isLoading } = useQuery({
    queryKey: ["folder-scopes", account.id],
    queryFn: () => getFolderScopes(account.id),
    retry: false,
  });

  const mutation = useMutation({
    mutationFn: (paths: string[]) => setFolderScopes(account.id, paths),
    onSuccess: () => {
      setNewPath("");
      setDraft(null);
      void queryClient.invalidateQueries({ queryKey: ["folder-scopes"] });
    },
  });

  const paths = scope?.folder_paths ?? [];

  return (
    <section>
      <h4 className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-800">
        <FolderTree size={15} className="text-brand-500" />
        SharePoint folders
      </h4>
      <p className="mb-3 text-[12px] text-slate-500">
        The only folders this account can import from. Everything else in the
        library stays out of reach.
      </p>

      {isLoading ? (
        <Loader2 size={16} className="animate-spin text-brand-500" />
      ) : scope?.unrestricted ? (
        <div className="flex items-start gap-2 rounded-xl border border-accent-200 bg-accent-50 px-3 py-2">
          <AlertTriangle size={13} className="mt-0.5 shrink-0 text-accent-600" />
          <p className="text-[12px] text-accent-800">
            This is the platform account. It imports the entire library. Adding
            a folder below would restrict it to that folder only.
          </p>
        </div>
      ) : paths.length === 0 ? (
        <div className="flex items-start gap-2 rounded-xl border border-amber-200 bg-amber-50 px-3 py-2">
          <AlertTriangle size={13} className="mt-0.5 shrink-0 text-amber-500" />
          <p className="text-[12px] text-amber-800">
            No folders assigned. This account imports nothing from SharePoint —
            its users can still upload their own documents.
          </p>
        </div>
      ) : (
        <ul className="space-y-1.5">
          {paths.map((path) => (
            <li
              key={path}
              className="flex items-center gap-2 rounded-xl border border-gray-200 px-3 py-2"
            >
              <span className="min-w-0 flex-1 truncate font-mono text-[11px] text-slate-700">
                {path}
              </span>
              <button
                onClick={() =>
                  mutation.mutate(paths.filter((p) => p !== path))
                }
                disabled={mutation.isPending}
                aria-label={`Remove ${path}`}
                className="shrink-0 rounded-lg p-1 text-gray-300 transition-colors hover:bg-red-50 hover:text-red-500 disabled:opacity-40"
              >
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}

      {draft === null ? (
        <button
          onClick={() => setDraft("")}
          className="mt-2 flex items-center gap-1.5 text-[12px] font-semibold text-brand-600 hover:text-brand-800"
        >
          <Plus size={13} />
          Add folder
        </button>
      ) : (
        <div className="mt-2 flex gap-2">
          <input
            autoFocus
            value={newPath}
            onChange={(e) => setNewPath(e.target.value)}
            placeholder="RMP Master Directory/Airport - Safety Risk Management Documents/SEA"
            className="min-w-0 flex-1 rounded-xl border border-gray-200 px-3 py-2 font-mono text-[11px] text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
          />
          <button
            onClick={() => mutation.mutate([...paths, newPath.trim()])}
            disabled={!newPath.trim() || mutation.isPending}
            className="shrink-0 rounded-xl bg-brand-600 px-3 py-2 text-[12px] font-semibold text-white hover:bg-brand-700 disabled:opacity-40"
          >
            <Check size={14} />
          </button>
          <button
            onClick={() => {
              setDraft(null);
              setNewPath("");
            }}
            className="shrink-0 rounded-xl border border-gray-200 px-3 py-2 text-[12px] text-slate-500 hover:bg-gray-50"
          >
            <X size={14} />
          </button>
        </div>
      )}

      {mutation.isError && (
        <div className="mt-2 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          That folder was rejected. It must sit inside the configured airport
          documents root.
        </div>
      )}
    </section>
  );
}

function MembersSection({ account }: { account: OrganizationSummary }) {
  const queryClient = useQueryClient();
  const { profile } = useUserRole();
  const [email, setEmail] = useState("");
  const [role, setRole] = useState<MembershipRole>("analyst");
  const [removeConfirm, setRemoveConfirm] = useState<string | null>(null);

  const { data: members = [], isLoading } = useQuery({
    queryKey: ["organization-members", account.id],
    queryFn: () => getOrganizationMembers(account.id),
    retry: false,
  });

  const invalidate = () => {
    void queryClient.invalidateQueries({
      queryKey: ["organization-members", account.id],
    });
  };

  const addMutation = useMutation({
    mutationFn: () => addMember(account.id, { email: email.trim(), role }),
    onSuccess: () => {
      setEmail("");
      invalidate();
    },
  });

  const platformAdminMutation = useMutation({
    mutationFn: ({ userId, grant }: { userId: string; grant: boolean }) =>
      setPlatformAdmin(userId, grant),
    onSuccess: invalidate,
  });

  const removeMutation = useMutation({
    mutationFn: (userId: string) => removeMember(account.id, userId),
    onSuccess: () => {
      setRemoveConfirm(null);
      invalidate();
    },
  });

  function handleRemove(userId: string) {
    if (removeConfirm === userId) {
      removeMutation.mutate(userId);
    } else {
      setRemoveConfirm(userId);
      setTimeout(() => setRemoveConfirm(null), 3000);
    }
  }

  return (
    <section>
      <h4 className="mb-1 flex items-center gap-2 text-sm font-semibold text-slate-800">
        <UserPlus size={15} className="text-brand-500" />
        Users
      </h4>
      <p className="mb-3 text-[12px] text-slate-500">
        Adding a user sends them a Microsoft invitation. Account admins can add
        their own colleagues; analysts and viewers cannot. The shield grants
        platform administration — full access to every account and the AI
        configuration, so use it only for Faith Group staff.
      </p>

      <div className="mb-3 flex gap-2">
        <input
          type="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          placeholder="name@seattleairport.org"
          className="min-w-0 flex-1 rounded-xl border border-gray-200 px-3 py-2 text-sm text-slate-800 focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-500/20"
        />
        <select
          value={role}
          onChange={(e) => setRole(e.target.value as MembershipRole)}
          aria-label="Role"
          className="shrink-0 rounded-xl border border-gray-200 px-3 py-2 text-[12px] text-slate-700 focus:border-brand-500 focus:outline-none"
        >
          {ROLE_ORDER.map((r) => (
            <option key={r} value={r}>
              {ROLE_LABELS[r]}
            </option>
          ))}
        </select>
        <button
          onClick={() => addMutation.mutate()}
          disabled={!email.trim() || addMutation.isPending}
          className="flex shrink-0 items-center gap-1.5 rounded-xl bg-brand-600 px-3 py-2 text-[12px] font-semibold text-white hover:bg-brand-700 disabled:opacity-40"
        >
          {addMutation.isPending && (
            <Loader2 size={13} className="animate-spin" />
          )}
          Add
        </button>
      </div>

      {addMutation.isError && (
        <div className="mb-3 rounded-xl border border-red-200 bg-red-50 px-3 py-2 text-[12px] text-red-700">
          That user could not be added. Check the address and try again.
        </div>
      )}

      {isLoading ? (
        <Loader2 size={16} className="animate-spin text-brand-500" />
      ) : members.length === 0 ? (
        <p className="rounded-xl border border-gray-200 px-3 py-4 text-center text-[12px] text-slate-400">
          No users yet.
        </p>
      ) : (
        <ul className="space-y-1.5">
          {members.map((member: OrganizationMember) => (
            <li
              key={member.id}
              className="flex items-center gap-3 rounded-xl border border-gray-200 px-3 py-2"
            >
              <div className="min-w-0 flex-1">
                <div className="truncate text-[13px] font-medium text-slate-800">
                  {member.display_name || member.email}
                </div>
                <div className="truncate text-[11px] text-slate-400">
                  {member.email}
                </div>
              </div>
              <span className="shrink-0 rounded-full bg-gray-100 px-2 py-0.5 text-[10px] font-bold text-slate-600">
                {ROLE_LABELS[member.role]}
              </span>
              {member.invitation_status === "invited" && (
                <span className="shrink-0 rounded-full bg-accent-50 px-2 py-0.5 text-[10px] font-bold text-accent-700">
                  Invited
                </span>
              )}
              <button
                onClick={() =>
                  platformAdminMutation.mutate({
                    userId: member.user_id,
                    grant: !member.is_platform_admin,
                  })
                }
                disabled={
                  platformAdminMutation.isPending ||
                  member.user_id === profile?.id
                }
                title={
                  member.user_id === profile?.id
                    ? "You cannot change your own platform access"
                    : member.is_platform_admin
                      ? "Platform administrator — click to revoke"
                      : "Grant platform administrator"
                }
                className={`shrink-0 rounded-lg p-1 transition-colors disabled:opacity-30 ${
                  member.is_platform_admin
                    ? "bg-brand-50 text-brand-600"
                    : "text-gray-300 hover:bg-brand-50 hover:text-brand-500"
                }`}
              >
                <ShieldCheck size={13} />
              </button>
              <button
                onClick={() => handleRemove(member.user_id)}
                disabled={removeMutation.isPending}
                title={
                  removeConfirm === member.user_id
                    ? "Click again to confirm removal"
                    : "Remove from this account"
                }
                className={`shrink-0 rounded-lg p-1 transition-colors disabled:opacity-40 ${
                  removeConfirm === member.user_id
                    ? "bg-red-50 text-red-500"
                    : "text-gray-300 hover:bg-red-50 hover:text-red-500"
                }`}
              >
                <Trash2 size={13} />
              </button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

// --- Shared modal chrome ---

function ModalShell({
  title,
  onClose,
  wide = false,
  children,
}: {
  title: string;
  onClose: () => void;
  wide?: boolean;
  children: React.ReactNode;
}) {
  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 p-4 backdrop-blur-sm"
      role="dialog"
      aria-modal="true"
      aria-label={title}
    >
      <div
        className={`flex max-h-[85vh] w-full flex-col overflow-hidden rounded-2xl border border-gray-200 bg-white shadow-2xl ${
          wide ? "max-w-2xl" : "max-w-lg"
        }`}
      >
        <div className="flex items-center justify-between border-b border-gray-100 bg-gray-50 px-6 py-4">
          <h3 className="truncate text-sm font-semibold text-gray-900">{title}</h3>
          <button
            onClick={onClose}
            aria-label="Close"
            className="shrink-0 rounded-lg p-1.5 text-gray-400 hover:bg-gray-200 hover:text-gray-600"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-6 py-5">{children}</div>
      </div>
    </div>
  );
}

function ModalActions({
  onClose,
  onSubmit,
  submitLabel,
  disabled,
  pending,
}: {
  onClose: () => void;
  onSubmit: () => void;
  submitLabel: string;
  disabled: boolean;
  pending: boolean;
}) {
  return (
    <div className="mt-5 flex justify-end gap-2">
      <button
        onClick={onClose}
        className="rounded-xl border border-gray-200 px-4 py-2 text-sm font-semibold text-slate-600 hover:bg-gray-50"
      >
        Cancel
      </button>
      <button
        onClick={onSubmit}
        disabled={disabled || pending}
        className="flex items-center gap-2 rounded-xl bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-40"
      >
        {pending && <Loader2 size={14} className="animate-spin" />}
        {submitLabel}
      </button>
    </div>
  );
}
