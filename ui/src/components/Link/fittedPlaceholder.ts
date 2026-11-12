import { computed, onBeforeUnmount, ref } from "vue";

/**
 * A placeholder cut to the input's width, ending in "…". A focused input hard-cuts its placeholder whatever
 * `text-overflow` says, so the text itself is shortened. `fit` takes the input once it has focus; until then
 * the full text shows and `text-overflow` cuts it.
 */
export function useFittedPlaceholder(text: () => string) {
  const room = ref(Infinity);
  const font = ref("");
  const spacing = ref("0px");
  let fitted: HTMLInputElement | null = null;
  let observer: ResizeObserver | null = null;
  let canvas: HTMLCanvasElement | null = null;

  function fit(input: HTMLInputElement) {
    if (input === fitted || typeof ResizeObserver === "undefined") return;
    observer?.disconnect();
    fitted = input;
    // The `font` shorthand reads empty when a longhand it cannot express is set.
    const style = getComputedStyle(input);
    font.value = `${style.fontStyle} ${style.fontWeight} ${style.fontSize} ${style.fontFamily}`;
    spacing.value = style.letterSpacing === "normal" ? "0px" : style.letterSpacing;
    canvas ??= document.createElement("canvas");
    // The text fits the content box: the padding stays clear.
    const padding = (parseFloat(style.paddingLeft) || 0) + (parseFloat(style.paddingRight) || 0);
    observer = new ResizeObserver(() => (room.value = input.clientWidth - padding));
    observer.observe(input);
  }
  onBeforeUnmount(() => observer?.disconnect());

  const placeholder = computed(() => {
    const full = text();
    const context = font.value && Number.isFinite(room.value) ? canvas?.getContext("2d") : null;
    if (!context) return full;
    context.font = font.value;
    context.letterSpacing = spacing.value;
    // Half a pixel of slack: the browser rounds the text's width up.
    const fits = (shown: string) => context.measureText(shown).width <= room.value - 0.5;
    if (fits(full)) return full;
    let keep = full.length;
    while (keep > 0 && !fits(`${full.slice(0, keep).trimEnd()}…`)) keep--;
    return `${full.slice(0, keep).trimEnd()}…`;
  });

  return { placeholder, fit };
}
