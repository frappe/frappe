import { h } from "vue"

// A frappe-ui menu row that is the current pick: marked, with a tick at its end, as the lists
// that pick a model, a level or a mode show it.
export function checked(option, isCurrent) {
	if (!isCurrent) return option
	return {
		...option,
		selected: true,
		slots: { suffix: () => h("span", { class: "lucide-check ml-auto size-4 flex-none text-ink-gray-7", "aria-hidden": "true" }) },
	}
}
