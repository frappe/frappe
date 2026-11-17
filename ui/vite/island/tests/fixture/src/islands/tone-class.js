// Sits between the components and `tone.js`, so one chunk imports another. The
// panel and the badge reach this module, and the `dot` entry reaches only
// `tone.js`, so the two land in separate chunks.
import { TONES } from "./tone.js";

export const toneClass = (delta) => (delta < 0 ? TONES.negative : TONES.positive);
