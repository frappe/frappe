// Addresses an overlay by `route.hash`: `#<root>/<segments…>` on whatever page
// the app is already on, so a dialog is linkable and Back-dismissable without a
// route of its own. Reads the router's own reactive hash, so no `hashchange`
// listener is involved.
import { computed } from "vue";
import type { ComputedRef } from "vue";
import { useRoute, useRouter } from "vue-router";

export interface UseHashDialog {
  /** Whether the current hash is this dialog's. */
  open: ComputedRef<boolean>;
  /** The segments after the root, decoded; empty while closed. */
  segments: ComputedRef<string[]>;
  /** Opens the dialog, or moves within it if it is already open. */
  write: (...segments: string[]) => void;
  /** Drops the hash, leaving any query untouched. */
  close: () => void;
}

export function useHashDialog(root: string): UseHashDialog {
  const route = useRoute();
  const router = useRouter();

  // Segments are read and written raw: the router percent-encodes the hash on
  // its way into the URL and decodes it on the way back out, and encoding here
  // too would have it escape our escapes.
  const ours = computed(() => {
    const [head, ...rest] = route.hash.replace(/^#/, "").split("/");
    return head === root ? rest : null;
  });

  const open = computed(() => ours.value !== null);
  const segments = computed(() => ours.value ?? []);

  // Push to open, replace for everything after: opening is the navigation Back
  // should undo, and a change within an open dialog is not navigation at all.
  function write(...path: string[]) {
    navigate(`#${[root, ...path].join("/")}`);
  }

  // Closing a dialog that is not the one addressed would throw away another
  // dialog's hash, so it is only ever our own hash that is dropped.
  function close() {
    if (open.value) router.replace({ query: route.query, hash: "" });
  }

  function navigate(hash: string) {
    const to = { query: route.query, hash };
    if (open.value) router.replace(to);
    else router.push(to);
  }

  return { open, segments, write, close };
}
