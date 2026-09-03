// What a script may ask about permissions: the rights dict, the session's roles, and a field's access.
import { watch, type ComputedRef, type Ref } from "vue";
import {
  useDocPermissions,
  type FieldAccess,
} from "@framework/ui/composables/useDocPermissions";
import { useUserRoles } from "@framework/ui/composables/useUserRoles";

/** Enforcement bookkeeping `getdoc` ships beside the rights. Closed list: the
 *  right set is open-ended (custom `Permission Type` rows), so never allowlist. */
const NON_RIGHTS = ["if_owner", "has_if_owner_enabled"];

export interface PagePermissionsHost {
  doctype: string;
  meta: Ref<any>;
  perms: () => Record<string, any>;
}

export interface PagePermissions {
  /** Every right frappe would check for this doctype, values `0` or `1`. */
  perms: () => Record<string, any>;
  roles: () => string[];
  fieldAccess: (fieldname: string) => FieldAccess;
  /** Resolves once roles and meta are in, so `page.roles` is never seen empty. */
  ready: () => Promise<void>;
}

export function createPagePermissions(
  host: PagePermissionsHost,
): PagePermissions {
  const { fieldAccess, loading } = useDocPermissions(() => host.doctype);
  const { roles } = useUserRoles();
  const warned = new Set<string>();
  let rights: { from: Record<string, any>; view: Record<string, any> } | null =
    null;
  // One promise for every replay: `refresh` runs on each paint and each save.
  let loaded: Promise<void> | null = null;

  return {
    perms: () => {
      const from = host.perms();
      if (rights?.from !== from) rights = { from, view: rightsView(from) };
      return rights.view;
    },
    roles: () => roles.value ?? [],
    fieldAccess: (fieldname) => accessTo(fieldname),
    ready: () => (loaded ??= whenLoaded(loading)),
  };

  function rightsView(from: Record<string, any>) {
    const view: Record<string, any> = {};
    for (const [right, value] of Object.entries(from))
      if (!NON_RIGHTS.includes(right)) view[right] = value;
    return import.meta.env.DEV ? warnOnUnknownRight(view) : view;
  }

  // `get_rights` emits every right as a key, so a key that is absent from a
  // populated dict is a typo, not a right the user lacks.
  function warnOnUnknownRight(view: Record<string, any>) {
    return new Proxy(view, {
      get(target, key, receiver) {
        if (typeof key === "string" && !(key in target) && hasRights(target))
          warn(`page.perms.${key} is not a right on ${host.doctype}.`);
        return Reflect.get(target, key, receiver);
      },
    });
  }

  function hasRights(view: Record<string, any>) {
    return Object.keys(view).length > 0;
  }

  function accessTo(fieldname: string): FieldAccess {
    const fields = host.meta.value?.fields;
    if (!fields) return "write";
    const field = fields.find((one: any) => one.fieldname === fieldname);
    if (field) return fieldAccess(field);
    warn(
      `page.fieldAccess("${fieldname}") — no such field on ${host.doctype}.`,
    );
    return "none";
  }

  function warn(message: string) {
    if (!import.meta.env.DEV || warned.has(message)) return;
    warned.add(message);
    console.warn(`[record-page] ${message}`);
  }
}

/** Resolves the first time `loading` is false, then disposes its watcher. */
export function whenLoaded(loading: ComputedRef<boolean>): Promise<void> {
  if (!loading.value) return Promise.resolve();
  return new Promise((resolve) => {
    const stop = watch(loading, (still) => {
      if (still) return;
      stop();
      resolve();
    });
  });
}
