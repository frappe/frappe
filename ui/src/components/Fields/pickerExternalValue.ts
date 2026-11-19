import { nextTick, ref, useId, watch } from "vue";
import type { Ref } from "vue";

/** Shows a value set from outside: the picker ignores the model while focused or open, so mount it again. */
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

  // A picker being replaced blurs and would send the text it held: drop that write.
  function accept(next: string | null | undefined) {
    if (replacing) return false;
    sent = next || "";
    void nextTick(() => (sent = undefined));
    return true;
  }

  return { id, key, accept };
}
