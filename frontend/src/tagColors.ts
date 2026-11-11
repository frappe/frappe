// A tag's colour is stored on its Tag (the `color` Select, Helpdesk's names). Module state, filled
// by every read that names tags, so a chip anywhere reads it by name.
import { reactive } from "vue";

const GRAY = "bg-surface-gray-5";

// Full class names, so Tailwind's scanner sees each one.
export const TAG_COLORS: Readonly<Record<string, string>> = {
	Gray: GRAY,
	Black: "bg-surface-gray-10",
	Blue: "bg-surface-blue-6",
	Green: "bg-surface-green-6",
	Red: "bg-surface-red-6",
	Pink: "bg-surface-pink-6",
	Orange: "bg-surface-orange-6",
	Amber: "bg-surface-amber-6",
	Yellow: "bg-surface-yellow-6",
	Cyan: "bg-surface-cyan-6",
	Teal: "bg-surface-teal-6",
	Violet: "bg-surface-violet-6",
	Purple: "bg-surface-purple-6",
};

export const TAG_COLOR_NAMES = Object.keys(TAG_COLORS);

const stored = reactive(new Map<string, string>());

/** Takes a read's `tag_colors` part: each named tag's colour, `""` for one without. */
export function seedTagColors(colors: unknown) {
	if (!colors || typeof colors !== "object" || Array.isArray(colors)) return;
	for (const [tag, color] of Object.entries(colors)) {
		if (typeof color !== "string") continue;
		if (color) stored.set(tag, color);
		else stored.delete(tag);
	}
}

/** The dot class of a tag; one with no stored colour draws gray. */
export function tagColorClass(tag: string): string {
	return colorClass(stored.get(tag));
}

export function colorClass(color: string | undefined): string {
	return TAG_COLORS[color ?? ""] ?? GRAY;
}
