import { afterEach, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref, type App } from "vue";

vi.mock("vuedraggable", () => ({ default: { render: () => null } }));
vi.mock("../CanvasColumn.vue", () => ({ default: { render: () => null } }));
vi.mock("../AddFieldRow.vue", () => ({ default: { render: () => null } }));
vi.mock("../RuleMark.vue", () => ({ default: { render: () => null } }));
vi.mock("@/acts/dispatcher", () => ({ acts: { perform: vi.fn() } }));
vi.mock("../canvasMenu", () => ({ canvasMenu: () => [], selectOn: vi.fn() }));
vi.mock("frappe-ui", () => ({
	Button: { render: () => h("button") },
	// The real Dropdown reports its open state through v-model:open; the stub opens on a click.
	Dropdown: {
		props: ["open"],
		emits: ["update:open"],
		setup(_props: unknown, { emit }: { emit: (event: "update:open", open: boolean) => void }) {
			return () => h("span", { "data-dropdown": "", onClick: () => emit("update:open", true) });
		},
	},
}));

import CanvasSection from "../CanvasSection.vue";

let app: App | null = null;
const dom = document.createElement("div");

function mount() {
	const canvas = {
		editable: true,
		selection: ref(null),
		errorsAt: () => [],
		state: { definition: {} },
	};
	const section = { name: "main", label: "Main", columns: [] };
	app = createApp({ render: () => h(CanvasSection, { canvas: canvas as never, section: section as never }) });
	app.mount(dom);
}

afterEach(() => {
	app?.unmount();
	app = null;
});

it("hides the controls under a column's ring, unless the section's menu is open", async () => {
	mount();
	const controls = dom.querySelector("[data-canvas-controls]")!;
	expect(controls.className).toContain("group-has-[[data-canvas-column-ring]]/section:!opacity-0");
	expect(controls.className).not.toContain("!opacity-100");
	(dom.querySelector("[data-dropdown]") as HTMLElement).click();
	await nextTick();
	expect(controls.className).toContain("!opacity-100");
	expect(controls.className).not.toContain("column-ring");
});
