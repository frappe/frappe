import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref, type App } from "vue";
import { useFieldTypes } from "@framework/ui/FormLayout";
import { CommitKey, DocKey, ResolveFieldKey, UpdateKey } from "@framework/ui/FormLayout/types";
import CanvasField from "../CanvasField.vue";
import { DesignCanvas } from "../designCanvas";
import type { EditorState } from "../editorSource";
import { provideInertForm } from "../inertForm";
import { PendingEdits } from "../pendingEdits";

const FIELDS = [
	{ fieldname: "subject", label: "Subject", fieldtype: "Data" },
	{ fieldname: "customer", label: "Customer", fieldtype: "Link", options: "Customer" },
	{ fieldname: "status", label: "Status", fieldtype: "Select", options: "Open\nClosed" },
];

function canvas() {
	const state = {
		doctype: "Task Note",
		mode: "Design",
		modes: ["Design"],
		base_version: { doctype: "", layouts: {}, app_layouts: {} },
		custom: 1,
		module: "Desk",
		app_title: null,
		record_count: 0,
		value_counts: {},
		layouts: {},
		definition: { name: "Task Note", fields: FIELDS },
	} as EditorState;
	return new DesignCanvas(state, new PendingEdits({} as never, () => undefined));
}

let app: App | undefined;
let host: HTMLElement;
const fetch = vi.fn();
const pageDoc = ref<Record<string, unknown>>({});
const page = { pending: vi.fn(), commit: vi.fn(), discard: vi.fn(), rowChanged: vi.fn() };
const pageUpdate = vi.fn();

beforeEach(() => {
	vi.stubGlobal("fetch", fetch);
	host = document.createElement("div");
	document.body.appendChild(host);
	const Canvas = defineComponent({
		setup() {
			provideInertForm();
			const one = canvas();
			return () => FIELDS.map(({ fieldname }) => h(CanvasField, { canvas: one, fieldname }));
		},
	});
	app = createApp(Canvas);
	app.provide(CommitKey, page);
	app.provide(DocKey, pageDoc);
	app.provide(UpdateKey, pageUpdate);
	app.provide(ResolveFieldKey, useFieldTypes().resolve);
	app.mount(host);
});

afterEach(() => {
	app?.unmount();
	host.remove();
	vi.unstubAllGlobals();
});

describe("a field on the canvas", () => {
	it("draws the record page's control inside an inert box", () => {
		const drawn = [...host.querySelectorAll("[inert] .field")].map((el) => el.getAttribute("data-fieldname"));
		expect(drawn).toEqual(["subject", "customer", "status"]);
	});

	it("commits nothing and writes no document", async () => {
		const input = host.querySelector<HTMLInputElement>("[data-fieldname='subject'] input")!;
		input.value = "Typed";
		input.dispatchEvent(new Event("input"));
		input.dispatchEvent(new Event("change"));
		await nextTick();
		expect(page.pending).not.toHaveBeenCalled();
		expect(page.commit).not.toHaveBeenCalled();
		expect(pageUpdate).not.toHaveBeenCalled();
		expect(pageDoc.value).toEqual({});
	});

	it("sends no request, a Link field's search included", async () => {
		await nextTick();
		await new Promise((resolve) => setTimeout(resolve, 50));
		expect(fetch).not.toHaveBeenCalled();
	});
});
