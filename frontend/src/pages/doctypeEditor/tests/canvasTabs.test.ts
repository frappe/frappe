// The tab strip: an unlabelled first tab reads gray until it is selected, then takes normal ink.
import { afterEach, describe, expect, it, beforeAll } from "vitest";
import { loadText, TEXT_SURFACES } from "@/acts/actText";
import { createApp, h, nextTick, type App } from "vue";
// @ts-expect-error sortablejs ships no types here; it is the engine under vue-draggable-next
import Sortable from "sortablejs";
import CanvasTabs from "../CanvasTabs.vue";
import { DRAG_OPTIONS, TAB_DRAG_OPTIONS } from "../canvasDrops";
import { mountEditor, taskNote } from "./editorFixture";

// A value waits for its surface's text to load once; load it first so a click acts at once.
beforeAll(() => Promise.all(TEXT_SURFACES.map(loadText)));

let app: App | undefined;
let stop: (() => void) | undefined;
afterEach(() => {
	app?.unmount();
	stop?.();
	app = stop = undefined;
	document.body.innerHTML = "";
});

const section = (name: string) => ({
	name,
	sections: [{ name: `${name}_s`, columns: [{ name: `${name}_c`, fields: ["subject"] }] }],
});

function strip() {
	const state = taskNote();
	state.layouts.Details![0].layout = [section("details"), { ...section("more"), label: "More" }] as never;
	const editor = mountEditor(state);
	stop = editor.stop;
	const root = document.body.appendChild(document.createElement("div"));
	app = createApp({ render: () => h(CanvasTabs, { canvas: editor.canvas }) });
	app.mount(root);
	return root;
}

const tabs = (root: HTMLElement) => Array.from(root.querySelectorAll<HTMLElement>('[role="tab"]'));
const gray = (tab: HTMLElement) => tab.classList.contains("text-ink-gray-4");

describe("CanvasTabs", () => {
	it("keeps an unlabelled first tab gray while another tab is open", async () => {
		const root = strip();
		await nextTick();
		tabs(root)[1].click();
		await nextTick();
		expect(tabs(root)[0].textContent).toContain("Details");
		expect(gray(tabs(root)[0])).toBe(true);
		expect(gray(tabs(root)[1])).toBe(false);
	});

	it("gives an unlabelled first tab normal ink when it is selected", async () => {
		const root = strip();
		await nextTick();
		tabs(root)[0].click();
		await nextTick();
		expect(tabs(root)[0].getAttribute("aria-selected")).toBe("true");
		expect(gray(tabs(root)[0])).toBe(false);
		expect(tabs(root)[0].classList.contains("text-ink-gray-9")).toBe(true);
	});

	it("lets a press on a tab start its drag, but not one on the rename input", () => {
		expect([TAB_DRAG_OPTIONS.filter, DRAG_OPTIONS.filter]).toEqual(["input", "button, input"]);
	});

	it("takes a field on a tab's name but not another tab, which would drop it as a new field", async () => {
		const root = strip();
		await nextTick();
		const target = Sortable.get(root.querySelector<HTMLElement>("[data-canvas-tab]")!)!;
		const group = target.options.group as { checkPut: (to: unknown, from: unknown) => boolean };
		const listOf = (name: string) => ({ options: { group: { name } } });
		expect(group.checkPut(target, listOf("canvas-fields"))).toBe(true);
		expect(group.checkPut(target, listOf("canvas-tabs"))).toBe(false);
	});
});
