// The Cards picker's Image select: lists Attach Image fields, keeps a hidden one in use, and is off with none.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, type Component } from "vue";
import CardSettings from "../CardSettings.vue";

vi.mock("frappe-ui", () => ({
	Button: { template: "<button />" },
	Popover: { template: "<div><slot name='default' /></div>" },
	FormControl: {
		props: ["label", "options", "disabled", "modelValue"],
		template: "<div data-select :data-label='label' :data-disabled='disabled' :data-value='modelValue'>{{ options.map((o) => o.value).join(',') }}</div>",
	},
}));

const apps: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
});

function imageSelect(fields: unknown[], image: string | null) {
	const root = document.createElement("div");
	const app = createApp({
		render: () => h(CardSettings as Component, { meta: { fields }, title: "name", body: null, image, update: () => {} }),
	});
	app.mount(root);
	apps.push(app);
	return root.querySelector<HTMLElement>("[data-label='Image']")!;
}

describe("CardSettings image picker", () => {
	const fields = [
		{ fieldname: "cover", fieldtype: "Attach Image" },
		{ fieldname: "secret", fieldtype: "Attach Image", hidden: 1 },
		{ fieldname: "file", fieldtype: "Attach" },
	];

	it("lists the Attach Image fields that are not hidden", () => {
		const select = imageSelect(fields, null);
		expect(select.textContent).toBe(",cover");
		expect(select.dataset.disabled).not.toBe("true");
	});

	it("keeps a hidden image field that is in use", () => {
		expect(imageSelect(fields, "secret").textContent).toBe(",cover,secret");
	});

	it("is off when the doctype has no Attach Image field", () => {
		const select = imageSelect([fields[2]], null);
		expect(select.textContent).toBe("");
		expect(select.dataset.disabled).toBe("true");
	});
});
