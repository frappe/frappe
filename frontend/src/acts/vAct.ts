import type { Directive } from "vue";
import { acts } from "./dispatcher";

type ActMark = string | [name: string, value?: unknown];

const marks = new WeakMap<HTMLElement, [string, unknown?]>();

/** `v-act="'surface.name'"` or `v-act="['surface.name', value]"`: a click performs the act and `data-act` names it, which the CI check reads. */
export const vAct: Directive<HTMLElement, ActMark> = {
	mounted(el, { value }) {
		mark(el, value);
		el.addEventListener("click", () => void acts.perform(...marks.get(el)!));
	},
	updated: (el, { value }) => mark(el, value),
};

function mark(el: HTMLElement, value: ActMark) {
	const entry = Array.isArray(value) ? value : [value];
	marks.set(el, entry as [string, unknown?]);
	el.dataset.act = entry[0];
}
