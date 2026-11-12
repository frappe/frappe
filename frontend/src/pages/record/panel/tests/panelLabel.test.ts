// The label tip: it shows for a truncated label or a description, never for a short bare one, and
// a tap shows it in a popover on a touch screen. The `*` marks a required field.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, ref } from "vue";

vi.mock("frappe-ui", async (importOriginal) => ({
	...((await importOriginal()) as Record<string, unknown>),
	Tooltip: defineComponent({
		props: { disabled: Boolean, hoverDelay: Number },
		setup:
			(props, { slots }) =>
			() =>
				h("div", { "data-tooltip": props.disabled ? "off" : "on", "data-delay": props.hoverDelay }, [
					slots.default?.(),
					!props.disabled && h("div", { "data-tip": "" }, slots.content?.()),
				]),
	}),
	Popover: defineComponent({
		setup:
			(_props, { slots }) =>
			() =>
				h("div", { "data-popover": "" }, [slots.trigger?.(), h("div", { "data-tip": "" }, slots.default?.())]),
	}),
}));

import type { FieldNode } from "@framework/ui/FormLayout/types";
import PanelLabel from "../PanelLabel.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	delete (window as any).matchMedia;
	vi.unstubAllGlobals();
	delete (HTMLElement.prototype as any).clientWidth;
});

// jsdom has no layout or canvas: every character, the * and the ellipsis are 10px wide, the row 100px.
const FIT_ROOM = 100;
function fitTenPerCharacter() {
	vi.stubGlobal(
		"OffscreenCanvas",
		class {
			getContext() {
				return { font: "", measureText: (value: string) => ({ width: value.length * 10 }) };
			}
		}
	);
	Object.defineProperty(HTMLElement.prototype, "clientWidth", {
		configurable: true,
		get: () => FIT_ROOM,
	});
}

async function mount(field: Partial<FieldNode>, { touch = false } = {}) {
	fitTenPerCharacter();
	(window as any).matchMedia = (query: string) => ({
		matches: touch && query === "(pointer: coarse)",
		addEventListener() {},
		removeEventListener() {},
		addListener() {},
		removeListener() {},
	});
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({
			render: () => h(PanelLabel, { field: { fieldname: "f", fieldtype: "Data", ...field } as FieldNode }),
		})
	);
	app.mount(root);
	mounted.push(app);
	await nextTick();
	await nextTick();
	return root;
}

describe("the label tip", () => {
	it("stays off for a short label with no description", async () => {
		const root = await mount({ label: "Name" });
		expect(root.querySelector("[data-tooltip]")!.getAttribute("data-tooltip")).toBe("off");
		expect(root.querySelector("[data-tip]")).toBeNull();
	});

	it("shows the full label for a truncated one", async () => {
		const root = await mount({ label: "A very long label that does not fit" });
		expect(root.querySelector("[data-tooltip]")!.getAttribute("data-tooltip")).toBe("on");
		expect(root.querySelector("[data-tip]")!.textContent).toBe("A very long label that does not fit");
	});

	it("shows the description under a short label, and its links work", async () => {
		const root = await mount({ label: "Name", description: 'See <a href="/docs">the docs</a>' });
		expect(root.querySelector("[data-tooltip]")!.getAttribute("data-tooltip")).toBe("on");
		const tip = root.querySelector("[data-tip]")!;
		expect(tip.textContent).toContain("Name");
		expect(tip.querySelector("a")!.getAttribute("href")).toBe("/docs");
		expect(tip.querySelector("a")!.getAttribute("target")).toBe("_blank");
	});

	it("waits 500ms before it shows", async () => {
		const root = await mount({ label: "Name", description: "d" });
		expect(root.querySelector("[data-tooltip]")!.getAttribute("data-delay")).toBe("500");
	});

	it("caps the tip at 240 (max-w-56 plus the bubble's padding) and grays the description", async () => {
		const root = await mount({ label: "Name", description: "Why we ask" });
		const tip = root.querySelector("[data-tip] > div")!;
		expect(tip.className).toContain("max-w-56");
		expect(tip.querySelector("span")!.className).toContain("text-ink-gray-4");
	});

	it("turns on when the label changes to one that does not fit", async () => {
		fitTenPerCharacter();
		const label = ref("Name");
		const root = document.createElement("div");
		document.body.appendChild(root);
		const app = createApp(
			defineComponent({
				render: () => h(PanelLabel, { field: { fieldname: "f", fieldtype: "Data", label: label.value } as FieldNode }),
			})
		);
		app.mount(root);
		mounted.push(app);
		await nextTick();
		expect(root.querySelector("[data-tooltip]")!.getAttribute("data-tooltip")).toBe("off");
		label.value = "A very long label that does not fit";
		await nextTick();
		await nextTick();
		await nextTick();
		expect(root.querySelector("[data-tooltip]")!.getAttribute("data-tooltip")).toBe("on");
	});

	it("moves to a popover on a touch screen, with the same content", async () => {
		const root = await mount({ label: "Name", description: "Why we ask" }, { touch: true });
		expect(root.querySelector("[data-tooltip]")).toBeNull();
		expect(root.querySelector("[data-popover] [data-tip]")!.textContent).toContain("Name");
		expect(root.querySelector("[data-popover] [data-tip]")!.textContent).toContain("Why we ask");
	});

	it("draws no popover on a touch screen for a short bare label", async () => {
		const root = await mount({ label: "Name" }, { touch: true });
		expect(root.querySelector("[data-popover]")).toBeNull();
	});
});

describe("the required mark", () => {
	it("draws a red * after a required label", async () => {
		const root = await mount({ label: "Name", reqd: true });
		const mark = [...root.querySelectorAll("span")].find((el) => el.textContent === "*")!;
		expect(mark.className).toContain("text-ink-red-4");
		expect(mark.className).toContain("shrink-0");
		expect(mark.getAttribute("aria-label")).toBe("Required");
	});

	it("keeps the * after the cut text, and the cut text fits with the * beside it", async () => {
		const root = await mount({ label: "A very long label that does not fit", reqd: true });
		const text = root.querySelector("[aria-hidden]")!;
		// 100px less the 10px *, less a half pixel spare: six characters and the ellipsis.
		expect(text.textContent).toBe("A very\u2026");
		expect(text.nextElementSibling!.textContent).toBe("A very long label that does not fit");
		expect(text.nextElementSibling!.className).toContain("sr-only");
		expect(root.textContent).toContain("*");
	});

	it("cuts a label for a * that appears later, and whole again when it goes", async () => {
		fitTenPerCharacter();
		const reqd = ref(false);
		const root = document.createElement("div");
		document.body.appendChild(root);
		const app = createApp(
			defineComponent({
				render: () =>
					h(PanelLabel, {
						field: { fieldname: "f", fieldtype: "Data", label: "Nine char", reqd: reqd.value } as FieldNode,
					}),
			})
		);
		app.mount(root);
		mounted.push(app);
		await nextTick();
		expect(root.textContent).toBe("Nine char");
		reqd.value = true;
		await nextTick();
		await nextTick();
		await nextTick();
		expect(root.querySelector("[aria-hidden]")!.textContent).toBe("Nine ch\u2026");
		reqd.value = false;
		await nextTick();
		await nextTick();
		await nextTick();
		expect(root.textContent).toBe("Nine char");
	});

	it("leaves a label that fits whole", async () => {
		const root = await mount({ label: "Name", reqd: true });
		expect(root.querySelector("[aria-hidden]")).toBeNull();
		expect(root.textContent).toBe("Name*");
	});

	it("draws no * on an optional label", async () => {
		const root = await mount({ label: "Name" });
		expect(root.textContent).not.toContain("*");
	});
});
