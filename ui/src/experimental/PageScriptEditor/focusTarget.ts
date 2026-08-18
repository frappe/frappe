// Finding the thing to focus inside a layout that is still assembling itself.
//
// The editor pane marks where focus belongs with `[autofocus]` — the convention
// frappe-ui's `Dialog` reads — but the marked element is a wrapper, and what it
// wraps arrives late: `CodeEditor` `import()`s CodeMirror inside an async
// `onMounted`, so its contenteditable is an unpredictable number of frames
// behind the branch that holds it.

/** What a marker resolves to: a button, or CodeMirror's editable surface. */
export const FOCUSABLE = 'button:not([disabled]),[contenteditable="true"]';

/**
 * The first focusable element in `marker`, waited for rather than sampled — a
 * single look finds a button every time and a lazy code editor never.
 *
 * Resolves `null` if the marker leaves the document, or if `deadline` ms pass
 * without one appearing: a layout that never grows one must not poll forever.
 */
export function focusableIn(marker: HTMLElement, deadline = 2000) {
  const until = performance.now() + deadline;
  return new Promise<HTMLElement | null>((resolve) => {
    const look = () => {
      const found = marker.matches(FOCUSABLE)
        ? marker
        : marker.querySelector<HTMLElement>(FOCUSABLE);
      if (found || !marker.isConnected || performance.now() > until)
        return resolve(found);
      requestAnimationFrame(look);
    };
    look();
  });
}
