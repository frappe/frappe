// The tab strip: an unlabelled first tab reads gray until it is selected, then takes normal ink.
import { afterEach, describe, expect, it } from "vitest";
import { createApp, h, nextTick, type App } from "vue";
import CanvasTabs from "../CanvasTabs.vue";
import { mountEditor, taskNote } from "./editorFixture";

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
	state.layouts.Details[0].layout = [section("details"), { ...section("more"), label: "More" }] as never;
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
});
