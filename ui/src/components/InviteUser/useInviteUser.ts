import { computed, reactive } from "vue";
import { createResource } from "frappe-ui";
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

  // Emails already invited to this app (pending or accepted). The email field
  // excludes these from its suggestions so you can't re-invite someone who's
  // already in flight or has already joined.
  const invitedEmailsResource = createResource({
    url: "frappe.client.get_list",
    params: {
      doctype: "User Invitation",
      filters: { app_name: appName, status: ["in", ["Pending", "Accepted"]] },
      fields: ["email"],
      limit_page_length: 0,
    },
    auto: false,
    transform: (rows: Array<{ email: string }>): string[] =>
      rows.map((r) => r.email),
  });

  // Existing users suggested in the email field — enabled, real (non-Website)
  // users from the User doctype (NOT Contact). Driven by `searchUsers(query)`.
  const usersResource = createResource({
    url: "frappe.client.get_list",
    transform: (
      rows: Array<{ name: string; full_name?: string; user_image?: string }>
    ): UserOption[] =>
      rows.map((r) => ({
        label: r.full_name || r.name,
        value: r.name,
        avatar: r.user_image || undefined,
      })),
  });

  function searchUsers(query: string): void {
    usersResource.submit({
      doctype: "User",
      filters: { enabled: 1, user_type: ["!=", "Website User"] },
      or_filters: query
        ? [
            ["User", "name", "like", `%${query}%`],
            ["User", "full_name", "like", `%${query}%`],
          ]
        : undefined,
      fields: ["name", "full_name", "user_image"],
      order_by: "full_name asc",
      limit_page_length: 20,
    });
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
    invitedEmailsResource.reload();
    return result;
  }

  async function cancel(name: string): Promise<void> {
    await cancelResource.submit({ name, app_name: appName });
    pendingResource.reload();
    invitedEmailsResource.reload();
  }

  async function resend(name: string): Promise<void> {
    await resendResource.submit({ name, app_name: appName });
  }

  // Lazy initial fetch — runs once per controller (the panel calls it on mount).
  // Roles are a static host list; users for the email field stay on-demand via
  // `searchUsers`. So only the pending list + already-invited set are fetched here.
  let loaded = false;
  function load(): void {
    if (loaded) return;
    loaded = true;
    pendingResource.fetch();
    invitedEmailsResource.fetch();
  }

  const store = reactive({
    pendingInvites: computed<PendingInvitation[]>(
      () => (pendingResource.data as PendingInvitation[]) ?? []
    ),
    roles: roleOptions,
    users: computed<UserOption[]>(() => {
      const invited = new Set(
        (invitedEmailsResource.data as string[] | null) ?? []
      );
      const found = (usersResource.data as UserOption[] | null) ?? [];
      return found.filter((u) => !invited.has(u.value));
    }),
    loading: computed(() => Boolean(pendingResource.loading)),
    usersLoading: computed(() => Boolean(usersResource.loading)),
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
        invitedEmailsResource.error ??
        cancelResource.error ??
        resendResource.error ??
        usersResource.error ??
        null
    ),
    invite,
    cancel,
    resend,
    searchUsers,
    load,
    reload: () => {
      pendingResource.reload();
      invitedEmailsResource.reload();
    },
  }) as InviteStore;

  return store;
}
