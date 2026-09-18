import { computed, reactive, ref } from "vue";
import { createResource } from "frappe-ui";
import { listDocuments, searchDocuments } from "../../api";
import type {
  InviteResult,
  InviteStore,
  PendingInvitation,
  UserOption,
  UseInviteUserOptions,
} from "./types";

const API = "frappe.core.api.user_invitation";

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

  const pendingResource = createResource({
    url: `${API}.get_pending_invitations`,
    method: "GET",
    params: { app_name: appName },
    auto: false,
  });

  // Existing users suggested in the email field: enabled, real (non-Website) users,
  // minus anyone already invited to this app (pending or accepted).
  const users = ref<UserOption[]>([]);
  const usersLoading = ref(false);
  const usersError = ref<unknown>(null);
  let searchGeneration = 0;

  async function searchUsers(query: string): Promise<void> {
    const mine = ++searchGeneration;
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

  const inviteResource = createResource({
    url: `${API}.invite_by_email`,
    method: "POST",
  });

  const cancelResource = createResource({
    url: `${API}.cancel_invitation`,
    method: "PATCH",
  });

  const resendResource = createResource({
    url: `${API}.resend_invitation`,
    method: "POST",
  });

  async function invite(
    emails: string,
    roles: string[]
  ): Promise<InviteResult> {
    const result = (await inviteResource.submit({
      // `extraParams` first: the controller's core params (emails, roles,
      // redirect_to_path, app_name) must win, so a host extra can't silently
      // retarget the invite to a different app than the pending/invited lists poll.
      ...extraParams,
      emails,
      roles: transformRoles(roles),
      redirect_to_path: redirectPath,
      app_name: appName,
    })) as InviteResult;
    pendingResource.reload();
    return result;
  }

  async function cancel(name: string): Promise<void> {
    await cancelResource.submit({ name, app_name: appName });
    pendingResource.reload();
  }

  async function resend(name: string): Promise<void> {
    await resendResource.submit({ name, app_name: appName });
  }

  // Lazy initial fetch — runs once per controller (the panel calls it on mount).
  // Roles are a static host list; users for the email field stay on-demand via
  // `searchUsers`. So only the pending list is fetched here.
  let loaded = false;
  function load(): void {
    if (loaded) return;
    loaded = true;
    pendingResource.fetch();
  }

  const store = reactive({
    pendingInvites: computed<PendingInvitation[]>(
      () => (pendingResource.data as PendingInvitation[]) ?? []
    ),
    roles: roleOptions,
    users: computed<UserOption[]>(() => users.value),
    loading: computed(() => Boolean(pendingResource.loading)),
    usersLoading: computed(() => usersLoading.value),
    inviting: computed(() => Boolean(inviteResource.loading)),
    // surface which row is busy so a host acting on pending invites can show spinners
    cancellingName: computed<string | null>(() =>
      cancelResource.loading ? cancelResource.params?.name ?? null : null
    ),
    resendingName: computed<string | null>(() =>
      resendResource.loading ? resendResource.params?.name ?? null : null
    ),
    // Only the invite error is semantically the email field's — the panel binds
    // `error` to it. Background fetch/mutation failures go to `loadError` so a
    // permission error on the initial pending fetch doesn't light up a blank
    // email input; hosts can surface `loadError` however they like.
    error: computed(() => inviteResource.error ?? null),
    loadError: computed(
      () =>
        pendingResource.error ??
        cancelResource.error ??
        resendResource.error ??
        usersError.value ??
        null
    ),
    invite,
    cancel,
    resend,
    searchUsers,
    load,
    reload: () => {
      pendingResource.reload();
    },
  }) as InviteStore;

  return store;
}
