import { watch, type Ref } from "vue";

/**
 * The row a bare key acts on: the one under the pointer or holding focus, the later of the two.
 * Leaving a row hands the cursor to the other one; a row that unmounts under it drops it.
 */
export function useRowCursor(cursor: Ref<string | null>, rendered: () => string[]) {
  let hovered: string | null = null;
  let focused: string | null = null;

  function enter(value: string) {
    hovered = value;
    cursor.value = value;
  }

  function leave(value: string) {
    if (hovered === value) hovered = null;
    if (cursor.value === value) cursor.value = hovered ?? focused;
  }

  function focus(value: string) {
    focused = value;
    cursor.value = value;
  }

  function blur(value: string) {
    if (focused === value) focused = null;
    if (cursor.value === value) cursor.value = hovered ?? focused;
  }

  // An unmounted row fires no pointerleave or focusout.
  watch(rendered, (values) => {
    const kept = new Set(values);
    if (hovered && !kept.has(hovered)) hovered = null;
    if (focused && !kept.has(focused)) focused = null;
    if (cursor.value && !kept.has(cursor.value)) cursor.value = hovered ?? focused;
  });

  return { enter, leave, focus, blur };
}
