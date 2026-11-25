import { onBeforeUnmount, onMounted } from "vue";
import type { Ref } from "vue";

export interface Shortcut {
  keys?: string | string[];
  match?: (event: KeyboardEvent) => boolean;
  guard?: (event: KeyboardEvent) => boolean;
  action: (event: KeyboardEvent) => void;
}

/** Window shortcuts that stand down while typing or while another dialog sits over `root`. */
export function useShortcuts(
  root: Ref<HTMLElement | null>,
  shortcuts: Shortcut[],
) {
  function handler(event: KeyboardEvent) {
    if (isTyping(event) || coveredByDialog(event)) return;
    const shortcut = shortcuts.find(
      (item) => matches(item, event) && (!item.guard || item.guard(event)),
    );
    if (!shortcut) return;
    event.preventDefault();
    shortcut.action(event);
  }

  function coveredByDialog(event: KeyboardEvent) {
    const target = event.target as Element | null;
    const dialog = target?.closest?.('[role="dialog"], [role="alertdialog"]');
    return Boolean(dialog && root.value && !dialog.contains(root.value));
  }

  onMounted(() => window.addEventListener("keydown", handler));
  onBeforeUnmount(() => window.removeEventListener("keydown", handler));
}

function matches(shortcut: Shortcut, event: KeyboardEvent) {
  if (shortcut.match) return shortcut.match(event);
  const keys = Array.isArray(shortcut.keys) ? shortcut.keys : [shortcut.keys];
  return keys.includes(event.key);
}

function isTyping(event: KeyboardEvent) {
  const el = event.target as HTMLElement | null;
  if (!el) return false;
  return (
    el.isContentEditable ||
    ["INPUT", "TEXTAREA", "SELECT"].includes(el.tagName) ||
    Boolean(el.closest?.('[contenteditable="true"]'))
  );
}
