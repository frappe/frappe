import { computed, toValue } from "vue";
import type { ComputedRef, MaybeRefOrGetter } from "vue";
import { useDoctypeMeta } from "./useDoctypeMeta";
import { useUserRoles } from "./useUserRoles";

export type FieldAccess = "write" | "read" | "none";

export interface UseDocPermissions {
  /** Doc-level rights from `docinfo.permissions` (`getdoc`); false until provided. */
  can: (right: string) => boolean;
  /** Permlevels the user's roles hold `right` on, from the meta's DocPerm rows. */
  allowedPermlevels: (right: "read" | "write") => number[];
  /** What a permlevel'd field may render as. */
  fieldAccess: (field: { permlevel?: number }) => FieldAccess;
  /** True while roles or meta are still loading (field access is Write until then). */
  loading: ComputedRef<boolean>;
}

/**
 * The Vue port of desk's `frappe.perm`: doc-level rights come from the
 * server-computed `docinfo.permissions`, field-level permlevel access from the
 * meta's DocPerm rows crossed with the session user's roles. Display-only —
 * enforcement stays server-side (`getdoc` applies field-level read permissions).
 */
export function useDocPermissions(
  doctype: MaybeRefOrGetter<string>,
  docPermissions?: MaybeRefOrGetter<Record<string, unknown> | null | undefined>
): UseDocPermissions {
  const { meta, loading: metaLoading } = useDoctypeMeta(doctype);
  const { roles, loading: rolesLoading } = useUserRoles();

  const permlevels = computed(() => {
    if (!roles.value || !meta.value?.permissions) return null;
    const held = { read: new Set<number>(), write: new Set<number>() };
    for (const row of meta.value.permissions) {
      if (!roles.value.includes(row.role)) continue;
      if (row.read) held.read.add(row.permlevel ?? 0);
      if (row.write) held.write.add(row.permlevel ?? 0);
    }
    return held;
  });

  function allowedPermlevels(right: "read" | "write"): number[] {
    return [...(permlevels.value?.[right] ?? [])].sort((a, b) => a - b);
  }

  // Fail-open while roles/meta load: better a field the server refuses to save
  // than a form that flashes empty. Permlevel 0 is doc-level territory (`can`).
  function fieldAccess(field: { permlevel?: number }): FieldAccess {
    const permlevel = field.permlevel ?? 0;
    if (permlevel === 0 || !permlevels.value) return "write";
    if (permlevels.value.write.has(permlevel)) return "write";
    if (permlevels.value.read.has(permlevel)) return "read";
    return "none";
  }

  return {
    can: (right) => Boolean(toValue(docPermissions)?.[right]),
    allowedPermlevels,
    fieldAccess,
    loading: computed(() => metaLoading.value || rolesLoading.value),
  };
}
