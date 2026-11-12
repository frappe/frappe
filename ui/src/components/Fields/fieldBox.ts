import type { InjectionKey, Ref } from "vue";

/** The element a picker's list stays inside: a row's box looks up `[data-picker-bound]` from here. */
export const fieldBoxKey: InjectionKey<Ref<HTMLElement | null>> = Symbol("fieldBox");
