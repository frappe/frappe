// A third entry that shares `tone.js` with the other two and nothing else.
import { TONES } from "./tone.js";

export function mount(el) {
	el.className = TONES.positive;
	return { update() {}, unmount() {} };
}
