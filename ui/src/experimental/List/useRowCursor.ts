import type { Ref } from "vue";

/**
 * The row a bare key acts on: the one under the pointer or holding focus, the later of the two.
 * Leaving a row keeps it as the cursor while focus is still inside.
 */
export function useRowCursor(cursor: Ref<string | null>) {
  function enter(value: string) {
    cursor.value = value;
  }

  function leave(value: string, event: Event) {
    const row = event.currentTarget as HTMLElement | null;
    if (cursor.value !== value || row?.contains(document.activeElement)) return;
    cursor.value = null;
  }

  return { enter, leave };
}
