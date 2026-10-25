/** Puts the cursor in a field's cell: a rich-text body before any input, so not its toolbar. */
export function focusField(cell: HTMLElement): void {
  const target = focusTarget(cell);
  if (target) {
    target.focus();
    return;
  }
  // A lazy control draws its input after the cell; it takes focus then, unless focus moved first.
  const from = document.activeElement;
  const observer = new MutationObserver(() => {
    const drawn = focusTarget(cell);
    if (!drawn) return;
    stop();
    if (document.activeElement === from) drawn.focus();
  });
  const stop = () => {
    observer.disconnect();
    document.removeEventListener("focusin", stop);
  };
  observer.observe(cell, { childList: true, subtree: true });
  document.addEventListener("focusin", stop);
}

function focusTarget(cell: HTMLElement): HTMLElement | null {
  return (
    cell.querySelector<HTMLElement>('[contenteditable="true"]') ??
    cell.querySelector<HTMLElement>("input, textarea, select, button")
  );
}
