import type { InjectionKey, Ref } from "vue";

/** A row's box: the selection bar stays inside it; a picker's list looks up `[data-picker-bound]`. */
export const fieldBoxKey: InjectionKey<Ref<HTMLElement | null>> = Symbol("fieldBox");
