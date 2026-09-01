import { computed, effectScope, isRef } from "vue";
import type { ComputedRef, Ref } from "vue";

export interface MemoizedState<Input, State> {
  /** The state for this input, built once and shared by every later caller. */
  get: (input: Input) => State;
  /** Drops every state, so one test cannot reach the next. */
  reset: () => void;
}

/**
 * Memoises state per key, in a detached scope so it outlives whichever component
 * asked for it first — a scope of its own would stop with that component.
 */
export function memoizedState<Input, State>(
  keyOf: (input: Input) => string,
  build: (input: Input) => State
): MemoizedState<Input, State> {
  const states = new Map<string, State>();

  return {
    get(input) {
      const key = keyOf(input);
      const existing = states.get(key);
      if (existing) return existing;

      const state = effectScope(true).run(() => build(input)) as State;
      states.set(key, state);
      return state;
    },
    reset() {
      states.clear();
    },
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
