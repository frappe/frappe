import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type App } from "vue";
import ExportDialog from "../ExportDialog.vue";

const fake = vi.hoisted(() => ({ shown: [] as Record<string, unknown>[], bundle: { fields: [] } }));

vi.mock("@framework/ui/ExportTemplate", async () => {
	const { defineComponent, h } = await import("vue");
	return {
		fetchDoctypeBundle: vi.fn(async () => fake.bundle),
		TemplateModal: defineComponent({
			inheritAttrs: false,
			setup: (_props, { attrs }) =>
				() => (fake.shown.push({ ...attrs }), h("div", { "data-template-modal": "" })),
		}),
	};
});

let mounted: App | null = null;

async function mount(selection: Record<string, unknown>, count: number) {
	const host = document.createElement("div");
	document.body.append(host);
	mounted = createApp(
		defineComponent({ render: () => h(ExportDialog, { modelValue: true, doctype: "ToDo", selection, count } as never) })
	);
	mounted.mount(host);
	for (let turn = 0; turn < 4; turn++) await nextTick();
	return fake.shown.at(-1)!;
}

afterEach(() => {
	mounted?.unmount();
	mounted = null;
	document.body.innerHTML = "";
	fake.shown.length = 0;
});

describe("ExportDialog", () => {
	it("pins the Data Exporter to the selected names", async () => {
		const props = await mount({ names: ["A", "B"] }, 2);
		expect(props.doctype).toBe("ToDo");
		expect(props.pinned).toEqual({ filters: { name: ["in", ["A", "B"]] }, count: 2 });
		expect(props.doctypeMeta).toEqual(fake.bundle);
	});

	it("pins it to the filters when the run takes every matching record", async () => {
		const props = await mount({ filters: { status: ["=", "Open"] } }, 1240);
		expect(props.pinned).toEqual({ filters: { status: ["=", "Open"] }, count: 1240 });
	});
});
