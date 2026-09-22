import { computed, reactive, ref } from "vue";
import { listDocuments, runDocumentMethod, runMethod, searchDocuments } from "../../api";
import type {
  InviteResult,
  InviteStore,
  PendingInvitation,
  UserOption,
  UseInviteUserOptions,
} from "./types";

const API = "frappe.core.api.user_invitation";
const DOCTYPE = "User Invitation";
// the list read joins one row per role, so a page holds fewer invitations than rows
const PAGE = 500;

interface PendingRow {
  name: string;
  email: string;
  role: string | null;
}

/** Fold the joined rows back into one invitation per name, roles in row order. */
function groupPending(rows: PendingRow[]): PendingInvitation[] {
  const byName = new Map<string, PendingInvitation>();
  for (const row of rows) {
    const invitation = byName.get(row.name) ?? { name: row.name, email: row.email, roles: [] };
    if (row.role) invitation.roles.push(row.role);
    byName.set(row.name, invitation);
  }
  return [...byName.values()];
}

/**
 * Data plugin behind `InviteUser`. Wraps Frappe's `user_invitation` API plus the
 * user-suggestion lookup and returns a `reactive` controller.
 * Spread it onto the panel with `v-bind="controller"` — it's reactive, so members
 * bind as live values; don't destructure it (that would drop reactivity).
 *
 * Each call returns a *fresh* controller (no module-level cache — that went stale
 * across user/role changes and was never evicted). The backing reads are lazy:
 * nothing is fetched until `load()` runs (the panel calls it on mount), so creating
 * a controller that's never shown costs no requests.
 */
export function useInviteUser(options: UseInviteUserOptions = {}): InviteStore {
  const appName = options.appName ?? "frappe";

  const redirectPath = options.redirectPath ?? "/app";
  const transformRoles = options.transformRoles ?? ((roles) => roles);
  const extraParams = options.extraParams ?? {};

  // Roles offered in the picker are supplied by the host as a static list (the
  // framework no longer derives them from the app's `user_invitation` hook); the
  // backend still verifies them at invite time for apps that declare one.
  const roleOptions = options.roles ?? [];

  const pendingInvites = ref<PendingInvitation[]>([]);
  const loading = ref(false);
  const pendingError = ref<unknown>(null);

  // a later read supersedes an earlier one still paging, so the stale rows never land
  let pendingGeneration = 0;

  async function fetchPending(): Promise<void> {
    const mine = ++pendingGeneration;
    loading.value = true;
    try {
      const rows: PendingRow[] = [];
      let start = 0;
      let more = true;
      while (more) {
        const page = await listDocuments<PendingRow>(DOCTYPE, {
          filters: { status: "Pending", app_name: appName },
          fields: ["name", "email", "roles.role"],
          order_by: "creation asc",
          start,
          limit: PAGE,
        });
        rows.push(...page.data);
        more = page.has_next_page;
        start += PAGE;
      }
      if (mine !== pendingGeneration) return;
      pendingInvites.value = groupPending(rows);
      pendingError.value = null;
    } catch (failure) {
      if (mine === pendingGeneration) pendingError.value = failure;
    } finally {
      if (mine === pendingGeneration) loading.value = false;
    }
  }

  // Existing users suggested in the email field: enabled, real (non-Website) users,
  // minus anyone already invited to this app (pending or accepted).
  const users = ref<UserOption[]>([]);
  const usersLoading = ref(false);
  const usersError = ref<unknown>(null);
  let searchGeneration = 0;
  // The last query typed, so a successful invite can drop the invited person from the suggestions.
  let currentQuery: string | null = null;

  async function searchUsers(query: string): Promise<void> {
    const mine = ++searchGeneration;
    currentQuery = query;
    usersLoading.value = true;
    try {
      const { data: found } = await searchDocuments("User", {
        txt: query,
        filters: { enabled: 1, user_type: ["!=", "Website User"] },
        limit: 20,
      });
      const invited = await invitedAmong(found.map((row) => row.value));
      if (mine !== searchGeneration) return;
      users.value = found
        .filter((row) => !invited.has(row.value))
        .map((row) => ({ label: row.label || row.value, value: row.value }));
      usersError.value = null;
    } catch (failure) {
      if (mine === searchGeneration) usersError.value = failure;
    } finally {
      if (mine === searchGeneration) usersLoading.value = false;
    }
  }

  async function invitedAmong(emails: string[]): Promise<Set<string>> {
    if (!emails.length) return new Set();
    const { data } = await listDocuments<{ email: string }>("User Invitation", {
      filters: {
        app_name: appName,
        status: ["in", ["Pending", "Accepted"]],
        email: ["in", emails],
      },
      fields: ["email"],
      limit: emails.length,
    });
    return new Set(data.map((row) => row.email));
  }

  const inviting = ref(false);
  const inviteError = ref<unknown>(null);
  const cancellingName = ref<string | null>(null);
  const cancelError = ref<unknown>(null);
  const resendingName = ref<string | null>(null);
  const resendError = ref<unknown>(null);

  async function invite(
    emails: string,
    roles: string[]
  ): Promise<InviteResult> {
    inviting.value = true;
    try {
      const { data: result } = await runMethod<InviteResult>(`${API}.invite_by_email`, {
        // `extraParams` first, so the core params (emails, roles, redirect_to_path, app_name)
        // win and a host extra cannot retarget the invite to another app.
        ...extraParams,
        emails,
        roles: transformRoles(roles),
        redirect_to_path: redirectPath,
        app_name: appName,
      });
      inviteError.value = null;
      void fetchPending();
      if (currentQuery !== null) void searchUsers(currentQuery);
      return result;
    } catch (failure) {
      inviteError.value = failure;
      throw failure;
    } finally {
      inviting.value = false;
    }
  }

  async function cancel(name: string): Promise<void> {
    cancellingName.value = name;
    try {
      await runDocumentMethod(DOCTYPE, name, "cancel_invite");
      cancelError.value = null;
      void fetchPending();
    } catch (failure) {
      cancelError.value = failure;
      throw failure;
    } finally {
      cancellingName.value = null;
    }
  }

  async function resend(name: string): Promise<void> {
    resendingName.value = name;
    try {
      await runDocumentMethod(DOCTYPE, name, "resend_invite", {}, { nullable: true });
      resendError.value = null;
    } catch (failure) {
      resendError.value = failure;
      throw failure;
    } finally {
      resendingName.value = null;
    }
  }

  // Lazy initial fetch — runs once per controller (the panel calls it on mount).
  // Roles are a static host list; users for the email field stay on-demand via
  // `searchUsers`. So only the pending list is fetched here.
  let loaded = false;
  function load(): void {
    if (loaded) return;
    loaded = true;
    void fetchPending();
  }

  const store = reactive({
    pendingInvites: computed<PendingInvitation[]>(() => pendingInvites.value),
    roles: roleOptions,
    users: computed<UserOption[]>(() => users.value),
    loading: computed(() => loading.value),
    usersLoading: computed(() => usersLoading.value),
    inviting: computed(() => inviting.value),
    // surface which row is busy so a host acting on pending invites can show spinners
    cancellingName: computed<string | null>(() => cancellingName.value),
    resendingName: computed<string | null>(() => resendingName.value),
    // Only the invite error is semantically the email field's — the panel binds
    // `error` to it. Background fetch/mutation failures go to `loadError` so a
    // permission error on the initial pending fetch doesn't light up a blank
    // email input; hosts can surface `loadError` however they like.
    error: computed(() => inviteError.value ?? null),
    loadError: computed(
      () =>
        pendingError.value ??
        cancelError.value ??
        resendError.value ??
        usersError.value ??
        null
    ),
    invite,
    cancel,
    resend,
    searchUsers,
    load,
    reload: () => {
      void fetchPending();
    },
  }) as InviteStore;

  return store;
}
