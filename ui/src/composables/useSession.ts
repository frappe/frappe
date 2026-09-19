// The signed-in person: published by a host that has already booted, fetched once by anyone else.
import { computed, getCurrentInstance, inject, ref, shallowRef } from "vue";
import type { App, ComputedRef, InjectionKey, Ref } from "vue";
import { getSession } from "../api";
import type { Session } from "../api";

/** Provided by the host app through `provideSession`; it always carries the module's own ref. */
export const SessionKey: InjectionKey<Ref<Session | null>> = Symbol("session");

export interface UseSession {
  /** The session, `null` until it is published or the first fetch lands. */
  session: ComputedRef<Session | null>;
  loading: ComputedRef<boolean>;
  error: ComputedRef<unknown>;
  reload: () => Promise<void>;
}

const store = shallowRef<Session | null>(null);
const loading = ref(false);
const error = ref<unknown>(null);
let generation = 0;
let started = false;

export function useSession(): UseSession {
  // `inject` warns when there is no component instance, and plain module code calls this
  // through `useUserRoles`; the module ref is the store in that case anyway.
  const shared = getCurrentInstance() ? inject(SessionKey, store) : store;
  if (!shared.value && !started) void fetchSession();

  return {
    session: computed(() => shared.value),
    loading: computed(() => loading.value),
    error: computed(() => error.value),
    reload: fetchSession,
  };
}

/** The host publishes the session it already has, so no caller fetches it again. */
export function setSession(session: Session): void {
  store.value = session;
  started = true;
}

export function provideSession(app: App, session: Session): void {
  setSession(session);
  app.provide(SessionKey, store);
}

/** Synchronous read, for plain functions that cannot call `inject`. */
export function currentSession(): Session | null {
  return store.value;
}

/** Drops the session and the one-shot flag, so one test cannot reach the next. */
export function resetSession(): void {
  generation++;
  store.value = null;
  loading.value = false;
  error.value = null;
  started = false;
}

// An answer that lands after a reset or a later reload is dropped rather than published.
async function fetchSession(): Promise<void> {
  const mine = ++generation;
  started = true;
  loading.value = true;
  try {
    const envelope = await getSession();
    if (mine !== generation) return;
    store.value = envelope.data;
    error.value = null;
  } catch (failure) {
    if (mine === generation) error.value = failure;
  } finally {
    if (mine === generation) loading.value = false;
  }
}
