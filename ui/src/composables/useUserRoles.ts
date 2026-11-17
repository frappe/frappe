import { computed } from "vue";
import type { ComputedRef } from "vue";
import { createResource, frappeRequest } from "frappe-ui";

export interface UseUserRoles {
  /** The session user's roles; `null` until they load. */
  roles: ComputedRef<string[] | null>;
  loading: ComputedRef<boolean>;
  reload: () => void;
}

/** One session, one user: fetched once and shared by every caller. */
let resource: any = null;

/**
 * Fetch the session user's roles (desk gets them from boot; hosts built on
 * `@framework/ui` fetch them here instead).
 */
export function useUserRoles(): UseUserRoles {
  resource ??= buildResource();

  return {
    roles: computed(() => (resource.data as string[] | undefined) ?? null),
    loading: computed(() => resource.loading),
    reload: () => resource.reload(),
  };
}

/** Drops the shared fetch, so one test's roles cannot reach the next. */
export function resetUserRoles(): void {
  resource = null;
}

function buildResource() {
  const created = createResource({
    url: "frappe.core.doctype.user.user.get_current_user_roles",
    cache: "User Roles",
    resourceFetcher: frappeRequest,
  });
  if (!created.fetched && !created.loading) created.fetch();
  return created;
}
