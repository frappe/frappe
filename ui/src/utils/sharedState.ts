import { computed, effectScope, isRef } from "vue";
import type { ComputedRef, Ref } from "vue";

export interface MemoizedState<Input, State> {
  /** The state for this input, built once and shared by every later caller. */
  get: (input: Input) => State;
  /** Sets every matching state aside; a holder keeps reading it, and the next `get` builds anew from it. */
  stale: (match: (key: string, state: State) => boolean) => void;
  /** Drops every state, so one test cannot reach the next. */
  reset: () => void;
}

/**
 * Memoises state per key, in a detached scope so it outlives whichever component
 * asked for it first — a scope of its own would stop with that component.
 */
export function memoizedState<Input, State>(
  keyOf: (input: Input) => string,
  build: (input: Input, stale?: State) => State
): MemoizedState<Input, State> {
  const states = new Map<string, State>();
  const staleStates = new Map<string, State>();

  return {
    get(input) {
      const key = keyOf(input);
      const existing = states.get(key);
      if (existing) return existing;

      const stale = staleStates.get(key);
      staleStates.delete(key);
      const state = effectScope(true).run(() => build(input, stale)) as State;
      states.set(key, state);
      return state;
    },
    stale(match) {
      for (const [key, state] of states) {
        if (!match(key, state)) continue;
        states.delete(key);
        staleStates.set(key, state);
      }
    },
    reset() {
      states.clear();
      staleStates.clear();
    },
  };
}

const holds = new Set<symbol>();
let held: (() => void)[] = [];

/** Shows a stale state's fresh value now, or, while a hold is open, with the rest when the last one ends. */
export function landFresh(commit: () => void): void {
  if (holds.size) held.push(commit);
  else commit();
}

/** Holds every fresh value back until the returned release, so a page shows them with its own reads. */
export function holdFresh(): () => void {
  const hold = Symbol("fresh");
  holds.add(hold);
  return () => {
    if (!holds.delete(hold) || holds.size) return;
    const commits = held;
    held = [];
    for (const commit of commits) commit();
  };
}

type Forwarded<State> = {
  [Key in keyof State]: State[Key] extends Ref<infer Value>
    ? ComputedRef<Value>
    : State[Key];
};

/**
 * One handle onto state that can be swapped underneath it: reads follow the current
 * state, calls land on it. Takes its shape from the state a factory builds.
 */
export function forwardState<State extends object>(
  current: () => State
): Forwarded<State> {
  const handle = {} as Record<string, unknown>;

  for (const [key, value] of Object.entries(current())) {
    handle[key] = isRef(value)
      ? computed(() => (current() as Record<string, Ref>)[key].value)
      : (...args: unknown[]) =>
          (current() as Record<string, (...args: unknown[]) => unknown>)[key](
            ...args
          );
  }

  return handle as Forwarded<State>;
}
