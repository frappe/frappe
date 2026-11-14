// The picker, mounted: it lists the sprite's names, narrows by search, and writes a name or "".
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick, ref } from "vue";

import IconPicker from "../IconPicker.vue";
import { resetSprite } from "../sprite";

const NAMES = [
	"star",
	"users",
	"mid-star",
	...Array.from({ length: 120 }, (_, i) => `zz-${i}`),
];
const SPRITE =
	'<svg id="frappe-symbols" style="display:none">' +
	NAMES.map(
		(name) => `<symbol id="icon-${name}" viewBox="0 0 24 24"></symbol>`,
	).join("") +
	"</svg>";

const value = ref("");
let host: HTMLElement;
let app: ReturnType<typeof createApp>;

async function settle() {
	for (let turn = 0; turn < 4; turn++) {
		await new Promise((resolve) => setTimeout(resolve, 0));
		await nextTick();
	}
}

async function mount(initial = "") {
	value.value = initial;
	host = document.createElement("div");
	document.body.appendChild(host);
	app = createApp({
		render: () =>
			h(IconPicker, {
				modelValue: value.value,
				"onUpdate:modelValue": (name: string) => (value.value = name),
			}),
	});
	app.mount(host);
	await settle();
}

const rows = () =>
	[...document.querySelectorAll('[role="option"]')].map((row) =>
		row.textContent?.trim(),
	);

async function openPicker() {
	const trigger = host.querySelector<HTMLElement>("button, [role=combobox]")!;
	trigger.dispatchEvent(
		new PointerEvent("pointerdown", { bubbles: true, button: 0 }),
	);
	trigger.click();
	await settle();
}

beforeEach(() => {
	document.body.innerHTML = "";
	resetSprite();
	vi.stubGlobal(
		"fetch",
		vi
			.fn()
			.mockResolvedValue({ ok: true, text: () => Promise.resolve(SPRITE) }),
	);
});

afterEach(() => {
	app.unmount();
	vi.unstubAllGlobals();
});

describe("the list", () => {
	it("offers Default icon first, then the sprite's names, capped", async () => {
		await mount();
		await openPicker();
		expect(rows()[0]).toBe("Default icon");
		expect(rows()).toContain("star");
		expect(rows()).toHaveLength(81);
	});

	it("lists names that start with the search before names that only contain it", async () => {
		await mount();
		await openPicker();
		const search = document.querySelector<HTMLInputElement>("input")!;
		search.value = "sta";
		search.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(rows()).toEqual(["star", "mid-star"]);
	});

	it("drops Default icon while searching, so the first match takes the highlight", async () => {
		await mount();
		await openPicker();
		const search = document.querySelector<HTMLInputElement>("input")!;
		search.value = "star";
		search.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(rows()[0]).toBe("star");
		expect(rows()).not.toContain("Default icon");
	});

	it("selects nothing while searching, so a non-matching current icon is not listed", async () => {
		await mount("users");
		await openPicker();
		const search = document.querySelector<HTMLInputElement>("input")!;
		search.value = "star";
		search.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(rows()).toEqual(["star", "mid-star"]);
		expect(host.querySelector("button")!.textContent).toContain("users");
	});

	it("says no icon matches for a search that finds none", async () => {
		await mount("users");
		await openPicker();
		const search = document.querySelector<HTMLInputElement>("input")!;
		search.value = "nothing-here";
		search.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(rows()).toEqual([]);
		expect(document.body.textContent).toContain("No icon matches");
	});

	it("narrows by the search, past the cap", async () => {
		await mount();
		await openPicker();
		const search = document.querySelector<HTMLInputElement>("input")!;
		search.value = "zz-119";
		search.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(rows()).toEqual(["zz-119"]);
	});
});

describe("choosing", () => {
	it("writes the name", async () => {
		await mount();
		await openPicker();
		[...document.querySelectorAll<HTMLElement>('[role="option"]')]
			.find((row) => row.textContent?.trim() === "users")!
			.click();
		await settle();
		expect(value.value).toBe("users");
	});

	it("lists every name again after a pick, whatever the last search was", async () => {
		await mount();
		await openPicker();
		[...document.querySelectorAll<HTMLElement>('[role="option"]')]
			.find((row) => row.textContent?.trim() === "users")!
			.click();
		await settle();
		value.value = "star";
		await openPicker();
		expect(rows()).toContain("star");
	});

	it("gives focus back to the trigger after a pick", async () => {
		await mount();
		await openPicker();
		[...document.querySelectorAll<HTMLElement>('[role="option"]')]
			.find((row) => row.textContent?.trim() === "users")!
			.click();
		await settle();
		expect(document.activeElement).toBe(host.querySelector("button"));
	});

	it("clears the value with Default icon", async () => {
		await mount("star");
		await openPicker();
		document.querySelectorAll<HTMLElement>('[role="option"]')[0].click();
		await settle();
		expect(value.value).toBe("");
	});

	it("lists a search with a space as hyphenated names", async () => {
		await mount();
		await openPicker();
		const search = document.querySelector<HTMLInputElement>("input")!;
		search.value = "mid star";
		search.dispatchEvent(new Event("input", { bubbles: true }));
		await settle();
		expect(rows()).toEqual(["mid-star"]);
	});

	it("keeps the current icon in the list even when the cap hides it", async () => {
		await mount("zz-119");
		await openPicker();
		expect(rows()).toContain("zz-119");
	});
});
