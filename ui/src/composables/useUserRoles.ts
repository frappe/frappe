import { computed } from "vue";
import type { ComputedRef } from "vue";
import { resetSession, useSession } from "./useSession";

export interface UseUserRoles {
  /** The session user's roles; `null` until they load. */
  roles: ComputedRef<string[] | null>;
  loading: ComputedRef<boolean>;
  reload: () => void;
}

/** The session user's roles, off the one shared session. */
export function useUserRoles(): UseUserRoles {
  const { session, loading, reload } = useSession();

  return {
    roles: computed(() => session.value?.roles ?? null),
    loading,
    reload: () => void reload(),
  };
}

/** Drops the shared session, so one test's roles cannot reach the next. */
export function resetUserRoles(): void {
  resetSession();
}
