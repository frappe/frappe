// A helper beside the component, holding class names as literals. A glob list
// forgets this shape. This failed once: an Insights list named the `.vue` files
// of a directory, and the class names lived in the `.ts` file next to them.
//
// Tailwind emits a class only where it reads the literal, so the names are
// spelled out. A name assembled at run time would draw nothing.
export const TONES = {
	positive: "text-ink-green-7",
	negative: "text-ink-red-7",
};

export const toneClass = (delta) => (delta < 0 ? TONES.negative : TONES.positive);
