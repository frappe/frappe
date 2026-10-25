/** Puts the cursor in a field's cell: a rich-text body before any input, so not its toolbar. */
export function focusField(cell: HTMLElement): void {
  const target = focusTarget(cell);
  if (target) {
    target.focus();
    return;
  }
  // A lazy control draws its input after the cell; it takes focus then, unless the reader moved it.
  const observer = new MutationObserver(() => {
    const drawn = focusTarget(cell);
    if (!drawn) return;
    observer.disconnect();
    if (document.activeElement === document.body) drawn.focus();
  });
  observer.observe(cell, { childList: true, subtree: true });
}

function focusTarget(cell: HTMLElement): HTMLElement | null {
  return (
    cell.querySelector<HTMLElement>('[contenteditable="true"]') ??
    cell.querySelector<HTMLElement>("input, textarea, select, button")
  );
}
