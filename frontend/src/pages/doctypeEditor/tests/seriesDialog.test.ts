// Naming Series in Settings: a read-only list, and an "Edit series" dialog that edits all at once.
import { afterEach, beforeEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, inject, nextTick, provide, type App } from "vue";

vi.mock("frappe-ui", async () => {
	const { defineComponent, h, inject, provide, watch } = await import("vue");
	return {
		Badge: defineComponent({ props: ["label"], setup: (p) => () => h("span", { "data-badge": "" }, p.label) }),
		Button: defineComponent({
			props: ["label", "disabled", "ariaLabel"],
			setup: (p) => () => h("button", { disabled: p.disabled, "aria-label": p.ariaLabel }, p.label),
		}),
		Dialog: defineComponent({
			props: ["open"],
			emits: ["afterLeave"],
			setup: (p, { slots, emit }) => {
				// The real Dialog fires after-leave once its close transition ends.
				watch(() => p.open, (open) => !open && emit("afterLeave"));
				return () => (p.open ? h("div", [slots.default?.(), slots.actions?.()]) : null);
			},
		}),
		TextInput: defineComponent({
			props: ["modelValue"],
			emits: ["update:modelValue"],
			setup: (p, { emit }) => () =>
				h("input", { value: p.modelValue, onInput: (e: Event) => emit("update:modelValue", (e.target as HTMLInputElement).value) }),
		}),
		RadioGroup: defineComponent({
			props: ["modelValue"],
			emits: ["update:modelValue"],
			setup: (p, { slots, emit }) => {
				provide("group", { get: () => p.modelValue, set: (value: unknown) => emit("update:modelValue", value) });
				return () => h("div", slots.default?.());
			},
		}),
		Radio: defineComponent({
			props: ["value"],
			setup: (p) => {
				const group = inject("group") as { get: () => unknown; set: (value: unknown) => void };
				return () => h("input", { type: "radio", checked: group.get() === p.value, onClick: () => group.set(p.value) });
			},
		}),
		Tooltip: defineComponent({ setup: (_p, { slots }) => () => h("span", slots.default?.()) }),
	};
});

import SettingsSeries from "../SettingsSeries.vue";
import { SettingsViewKey } from "../settingsView";

const setSeries = vi.fn();
const apps: App[] = [];
let field: { options: string; default: string };

beforeEach(() => {
	setSeries.mockReset();
	field = { options: "SINV-.YYYY.-\nRET-.YYYY.-", default: "SINV-.YYYY.-" };
});
afterEach(() => apps.splice(0).forEach((app) => app.unmount()));

function mount() {
	const view = {
		doctype: "Invoice",
		get fields() {
			return [{ fieldname: "naming_series", ...field }];
		},
		label: (fieldname: string) => fieldname,
		setSeries,
	};
	const Host = defineComponent({
		setup() {
			provide(SettingsViewKey, view as never);
			return () => h(SettingsSeries, { counters: {} });
		},
	});
	const root = document.createElement("div");
	document.body.append(root);
	const app = createApp(Host);
	app.mount(root);
	apps.push(app);
	return root;
}

const button = (root: HTMLElement, label: string) =>
	[...root.querySelectorAll("button")].find((one) => one.textContent === label) as HTMLButtonElement;
const inputs = (root: HTMLElement) => [...root.querySelectorAll("[data-series-dialog] input:not([type=radio])")] as HTMLInputElement[];
const radios = (root: HTMLElement) => [...root.querySelectorAll("input[type=radio]")] as HTMLInputElement[];

async function type(input: HTMLInputElement, text: string) {
	input.value = text;
	input.dispatchEvent(new Event("input"));
	await nextTick();
}

async function openDialog(root: HTMLElement) {
	button(root, "Edit series").click();
	await nextTick();
	await nextTick();
}

it("lists the series read-only, with the default marked and no inline editing", () => {
	const root = mount();
	expect([...root.querySelectorAll("[data-series]")].map((row) => row.getAttribute("data-series"))).toEqual(["SINV-.YYYY.-", "RET-.YYYY.-"]);
	expect(root.querySelectorAll("[data-badge]")).toHaveLength(1);
	expect(root.textContent).toContain("The series are the options of the Naming Series field.");
	expect(root.querySelector("input")).toBeNull();
	expect(button(root, "Make default")).toBeUndefined();
});

it("edits every series at once: Done writes the list with the chosen default first", async () => {
	const root = mount();
	await openDialog(root);
	expect(inputs(root).map((one) => one.value)).toEqual(["SINV-.YYYY.-", "RET-.YYYY.-"]);
	expect(radios(root).map((one) => one.checked)).toEqual([true, false]);

	await type(inputs(root)[1], "RET-NEW-.####");
	button(root, "Add a series").click();
	await nextTick();
	await type(inputs(root)[2], "EXP-.####");
	radios(root)[2].click();
	await nextTick();
	button(root, "Done").click();
	await nextTick();

	expect(setSeries).toHaveBeenCalledWith(["EXP-.####", "SINV-.YYYY.-", "RET-NEW-.####"], "EXP-.####");
	expect(root.querySelector("[data-series-dialog]")).toBeNull();
});

it("drops the edit on Cancel", async () => {
	const root = mount();
	await openDialog(root);
	await type(inputs(root)[0], "CHANGED");
	button(root, "Cancel").click();
	await nextTick();
	expect(setSeries).not.toHaveBeenCalled();
	await openDialog(root);
	expect(inputs(root)[0].value).toBe("SINV-.YYYY.-");
});

it("moves the default to the first series when the default row is removed, and keeps the last row", async () => {
	const root = mount();
	await openDialog(root);
	(root.querySelectorAll("button[aria-label='Remove series']")[0] as HTMLButtonElement).click();
	await nextTick();
	expect((root.querySelector("button[aria-label='Remove series']") as HTMLButtonElement).disabled).toBe(true);
	expect(radios(root).map((one) => one.checked)).toEqual([true]);
	button(root, "Done").click();
	await nextTick();
	expect(setSeries).toHaveBeenCalledWith(["RET-.YYYY.-"], "RET-.YYYY.-");
});

it("drops empty and repeated rows, and stages nothing when the series did not change", async () => {
	const root = mount();
	await openDialog(root);
	button(root, "Add a series").click();
	await nextTick();
	await type(inputs(root)[2], "  RET-.YYYY.-  ");
	button(root, "Done").click();
	await nextTick();
	expect(setSeries).not.toHaveBeenCalled();

	await openDialog(root);
	await type(inputs(root)[0], "");
	await type(inputs(root)[1], " ");
	expect(button(root, "Done").disabled).toBe(true);
});

it("stages nothing when Done keeps a default that is not the first series", async () => {
	field.default = "RET-.YYYY.-";
	const root = mount();
	await openDialog(root);
	button(root, "Done").click();
	await nextTick();
	expect(setSeries).not.toHaveBeenCalled();
});
