import { h, type Component } from "vue";

const drawn = new Map<string, Component>();
// Only a lucide name: the string becomes a CSS class, so it must not carry other classes.
const LUCIDE_NAME = /^lucide-[a-z0-9-]+$/;

/** A script row's `lucide-<name>` as the component the timeline's gutter draws; its class is bridged when the row is added. */
export function gutterIcon(icon?: string): Component | undefined {
	if (!icon || !LUCIDE_NAME.test(icon)) return undefined;
	let component = drawn.get(icon);
	if (!component) {
		component = () => h("span", { class: icon, "aria-hidden": "true" });
		drawn.set(icon, component);
	}
	return component;
}
