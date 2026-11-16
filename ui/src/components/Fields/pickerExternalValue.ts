import { nextTick, ref, useId, watch } from "vue";
import type { Ref } from "vue";

/**
 * Makes a frappe-ui date picker show a value set from outside (an act, a handler, a reset).
 * The picker keeps its text while its input has focus (or its calendar is open) and ignores
 * the model then, so the control mounts it again on such a change and gives focus back.
 * Bind `id` and `key` on the picker; send each write of the picker through `accept`.
 */
export function usePickerExternalValue(value: () => string | null | undefined, open: Ref<boolean>) {
  const id = useId();
  const key = ref(0);
  let sent: string | undefined;
  let replacing = false;

  watch(value, async (next) => {
    if (sent !== undefined && (next || "") === sent) return;
    const focused = document.activeElement?.id === id;
    if (!focused && !open.value) return;
    replacing = true;
    key.value++;
    await nextTick();
    replacing = false;
    if (focused) document.getElementById(id)?.focus();
  });

  /** False for a write of the picker being replaced: its blur would send the text it held. */
  function accept(next: string | null | undefined) {
    if (replacing) return false;
    sent = next || "";
    void nextTick(() => (sent = undefined));
    return true;
  }

  return { id, key, accept };
}
