import { nextTick, onBeforeUnmount } from "vue";
import type { Ref } from "vue";
import { getNode, isGroup } from "../tree";
import type { ConditionGroup, ConditionPath } from "../types";

/** Where focus goes after an edit. */
export type FocusTarget =
  | { kind: "row"; path: ConditionPath }
  | { kind: "add"; groupPath: ConditionPath };

/**
 * The row that slid into the deleted one's place, or the one before it for the
 * last row. A group pruned with it asks again one level up.
 */
export function focusAfterRemove<T>(
  root: ConditionGroup<T>,
  removed: ConditionPath
): FocusTarget {
  let path = removed;

  while (path.length > 0) {
    const groupPath = path.slice(0, -1);
    const node = getNode(root, groupPath);

    if (node !== undefined && isGroup(node)) {
      const count = node.conditions.length;
      if (count === 0) return { kind: "add", groupPath };
      const index = Math.min(path[path.length - 1], count - 1);
      return { kind: "row", path: [...groupPath, index] };
    }

    // That group was pruned too, so ask the same question about its own row.
    path = groupPath;
  }

  return { kind: "add", groupPath: [] };
}

/** The row just appended to `groupPath`. */
export function focusAfterAdd<T>(
  root: ConditionGroup<T>,
  groupPath: ConditionPath
): FocusTarget {
  const node = getNode(root, groupPath);
  if (node === undefined || !isGroup(node) || node.conditions.length === 0) {
    return { kind: "add", groupPath };
  }
  return { kind: "row", path: [...groupPath, node.conditions.length - 1] };
}

/**
 * The condition inside a new group, not the group's row, whose first focusable
 * is the and/or toggle.
 */
export function focusAfterAddGroup<T>(
  root: ConditionGroup<T>,
  groupPath: ConditionPath
): FocusTarget {
  const target = focusAfterAdd(root, groupPath);
  if (target.kind !== "row") return target;
  const added = getNode(root, target.path);
  if (added === undefined || !isGroup(added) || added.conditions.length === 0) {
    return target;
  }
  return { kind: "row", path: [...target.path, 0] };
}

const FOCUSABLE =
  'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])';

/** Where the user was standing when a row was removed. */
const ROW_ACTIONS = '[data-slot="condition-actions"] button';

/** Where the user is going when a row is added. */
const ROW_ENTRY =
  '[data-slot="condition-field"] button, [data-slot="condition-field"] input';

/** Fallback if a closing menu never returns focus to its trigger. */
const MENU_RESTORE_TIMEOUT = 300;

/**
 * Placing focus for one builder. Scoped by `builderId`, because two builders on
 * a page hold the same paths.
 */
export function useConditionFocus(
  builderId: string,
  rootRef: Ref<HTMLElement | null>
) {
  let cancelMenuFocus: (() => void) | null = null;
  const scope = `[data-condition-builder="${builderId}"]`;

  /**
   * By path, not a held ref: after a cascade the target is a row this group
   * never rendered.
   */
  function moveFocus(target: FocusTarget, after: "add" | "remove") {
    nextTick(() => {
      if (target.kind === "row") {
        const preferred = after === "remove" ? ROW_ACTIONS : ROW_ENTRY;
        const row = document.querySelector<HTMLElement>(
          `${scope}[data-condition-path="${target.path.join(".")}"]`
        );
        const element =
          ownElement(row, preferred) ?? ownElement(row, FOCUSABLE);
        element?.focus();
        return;
      }

      // Not path-scoped: the add cell sits outside any row.
      const add = firstEnabled(
        document.querySelector<HTMLElement>(
          `${scope}[data-add-group="${target.groupPath.join(".")}"]`
        ),
        "button"
      );
      // Nothing left to add into. The empty state carries tabindex="-1" to take
      // focus without being a button.
      const empty = rootRef.value?.querySelector<HTMLElement>(
        '[data-slot="condition-empty"]'
      );
      (add ?? empty)?.focus();
    });
  }

  /**
   * Focus the row at `path` after the closing menu has restored focus, which
   * lands a frame or more later.
   */
  function focusAfterMenuCloses(path: ConditionPath) {
    // Only ever one in flight: a second menu action supersedes the first.
    cancelMenuFocus?.();

    let timer: ReturnType<typeof setTimeout>;

    function stop() {
      document.removeEventListener("focusin", onFocusIn);
      clearTimeout(timer);
      cancelMenuFocus = null;
    }

    function place() {
      stop();
      moveFocus({ kind: "row", path }, "remove");
    }

    // A focusin outside this builder is the user moving deliberately, and
    // taking focus back would be worse than not placing it.
    function onFocusIn(event: FocusEvent) {
      const target = event.target;
      if (!(target instanceof Element)) return;
      if (target.closest(scope)) place();
      else stop();
    }

    timer = setTimeout(place, MENU_RESTORE_TIMEOUT);
    document.addEventListener("focusin", onFocusIn);
    cancelMenuFocus = stop;
  }

  // An unmount inside the wait would leave a listener focusing a builder that
  // is gone.
  onBeforeUnmount(() => cancelMenuFocus?.());

  return { moveFocus, focusAfterMenuCloses };
}

/**
 * The first match belonging to `row` itself, since a row holding a nested group
 * contains that whole subtree. Disabled elements are skipped.
 */
function ownElement(
  row: HTMLElement | null,
  selector: string
): HTMLElement | null {
  if (!row) return null;
  for (const element of row.querySelectorAll<HTMLElement>(selector)) {
    if (element.closest("[data-condition-path]") !== row) continue;
    if (element.hasAttribute("disabled")) continue;
    return element;
  }
  return null;
}

/** The first match that can actually take focus. */
function firstEnabled(
  root: HTMLElement | null,
  selector: string
): HTMLElement | null {
  if (!root) return null;
  for (const element of root.querySelectorAll<HTMLElement>(selector)) {
    if (!element.hasAttribute("disabled")) return element;
  }
  return null;
}
