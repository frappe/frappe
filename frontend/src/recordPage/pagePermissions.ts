// What a script may ask about permissions: the rights dict, the session's roles, and a field's access.
import type { Ref } from "vue";
import { useDocPermissions, type FieldAccess } from "@framework/ui/useDocPermissions";
import { useUserRoles } from "@framework/ui/useUserRoles";
import type { ActRight } from "@/acts/dispatcher";
import { doctypeRight, whenLoaded } from "@/acts/doctypeRight";

/** Enforcement bookkeeping the `permissions` part ships beside the rights. Closed list: the
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
  /** True once roles and meta are in, for a replay that must not wait. */
  loaded: () => boolean;
  /** An act's right: this doctype's from `perms`, another's from its meta's level 0 rows and the roles. */
  passes: (right: ActRight) => boolean;
  /** A promise while another doctype's meta loads, so `passes` cannot answer yet; else nothing. */
  settled: (right: ActRight) => Promise<void> | undefined;
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
    loaded: () => !loading.value,
    passes: (right) => {
      const on = rightOn(right);
      if (on.doctype === host.doctype) return Boolean(host.perms()[on.ptype]);
      return doctypeRight.passes(on);
    },
    settled: (right) => {
      const on = rightOn(right);
      return on.doctype === host.doctype ? undefined : doctypeRight.settled(on);
    },
  };

  function rightOn(right: ActRight) {
    return typeof right === "string" ? { doctype: host.doctype, ptype: right } : right;
  }

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
