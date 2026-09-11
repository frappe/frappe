// The quick actions row's overflow: a folded tag action opens its picker anchored under
// the menu, and the anchor's open flag does not outlive the action.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("../fittedActions", () => ({
	useFittedActions: () => ({ labelled: ref(0), visible: ref(0), fit: vi.fn() }),
}));

const seen = vi.hoisted(() => ({ open: [] as unknown[] }));

vi.mock("frappe-ui", () => {
	const Plain = (tag: string) =>
		defineComponent({ setup: (_, { slots }) => () => h(tag, slots.default?.()) });
	return {
		MultiSelect: defineComponent({
			props: ["open"],
			setup(props, { slots }) {
				return () => {
					seen.open.push(props.open);
					return h("div", { "data-picker": "" }, slots.trigger?.({ open: false }));
				};
			},
		}),
		Dropdown: defineComponent({
			props: ["options"],
			setup: (props, { slots }) => () =>
				h("div", [
					slots.default?.(),
					...props.options.map((option: any) =>
						h("button", { "data-menu-row": option.label, onClick: option.onClick })
					),
				]),
		}),
		Button: Plain("button"),
		Tooltip: Plain("span"),
		TooltipProvider: Plain("div"),
	};
});

import { PanelContextKey } from "../context";
import QuickActions from "../QuickActions.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	seen.open.splice(0);
});

function mount(actions: ReturnType<typeof ref<any[]>>) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(QuickActions) }));
	app.provide(PanelContextKey, {
		doctype: "CRM Deal",
		docname: "D-1",
		doc: ref({}),
		meta: ref(null),
		docinfo: ref({ permissions: { write: 1 } }),
		controller: { page: { call: vi.fn() }, quickActions: { visible: () => actions.value } } as any,
		run: vi.fn(),
		reloadDocinfo: vi.fn(async () => {}),
	});
	app.mount(root);
	mounted.push(app);
	return root;
}

describe("the overflow", () => {
	it("folds every action into the menu, and the Tags row opens the anchored picker", async () => {
		const actions = ref<any[]>([
			{ name: "print", label: "Print", icon: "lucide-printer" },
			{ name: "tags", label: "Tags", icon: "lucide-tag", tagging: true },
		]);
		const root = mount(actions);
		expect(root.querySelectorAll("[data-menu-row]")).toHaveLength(2);
		expect(seen.open.at(-1)).toBe(false);
		root.querySelector<HTMLElement>("[data-menu-row='Tags']")!.click();
		await nextTick();
		expect(seen.open.at(-1)).toBe(true);

		// The pick tags the record and the action goes; a later return must not pop the picker open.
		actions.value = [{ name: "print", label: "Print", icon: "lucide-printer" }];
		await nextTick();
		expect(root.querySelector("[data-picker]")).toBeNull();
		actions.value = [
			{ name: "print", label: "Print", icon: "lucide-printer" },
			{ name: "tags", label: "Tags", icon: "lucide-tag", tagging: true },
		];
		await nextTick();
		await nextTick();
		expect(seen.open.at(-1)).toBe(false);
	});
});
