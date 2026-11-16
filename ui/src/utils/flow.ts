import { frappeRequest } from "frappe-ui";
import { readonly, shallowRef } from "vue";
import type { Ref } from "vue";

export const FLOW_ENABLED_METHOD = "frappe.flow.api.is_enabled";

let state: Ref<boolean | null> | null = null;

/**
 * Whether Flow can chat on this site. The same for every user; check access to Flow separately.
 * Inside Desk it comes from `frappe.boot` at once. Elsewhere it is `null` until one request
 * answers, and `false` if that request fails.
 */
export function isFlowEnabled(): Readonly<Ref<boolean | null>> {
  if (!state) state = load();
  return readonly(state);
}

/** Drops the shared answer, so one test's site cannot reach the next. */
export function resetFlowEnabled(): void {
  state = null;
}

function load(): Ref<boolean | null> {
  const booted = (globalThis as any).frappe?.boot?.flow_enabled;
  if (typeof booted === "boolean") return shallowRef(booted);

  const loaded = shallowRef<boolean | null>(null);
  frappeRequest({ url: FLOW_ENABLED_METHOD, method: "GET" }).then(
    (enabled: unknown) => (loaded.value = Boolean(enabled)),
    () => (loaded.value = false),
  );
  return loaded;
}
