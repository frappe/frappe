// A Phone column's list cell draws the number with the apps' field actions at its end; a click on
// the button runs the action for its own cell and never follows the row's link.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick } from "vue";

import { FieldActionsKey } from "@framework/ui/fields/types";
import type { FieldAction } from "@framework/ui/fields/types";
import PhoneCell from "../PhoneCell.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

const action = (run = vi.fn()): FieldAction => ({
	act: "shell.crm.call",
	label: "Call",
	icon: "lucide-phone",
	run,
});

async function mount(value: string, actions: FieldAction[], onRowClick = vi.fn()) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({
			render: () =>
				h("a", { href: "#row", onClick: onRowClick }, [
					h(PhoneCell, { field: { fieldname: "mobile_no", fieldtype: "Phone" }, value }),
				]),
		})
	);
	app.provide(FieldActionsKey, { for: (_field, current) => (current ? actions : []) });
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

describe("a Phone list cell", () => {
	it("draws the number and runs the action for it without opening the row", async () => {
		const run = vi.fn();
		const onRowClick = vi.fn();
		const root = await mount("123", [action(run)], onRowClick);
		expect(root.textContent).toContain("123");
		const button = root.querySelector<HTMLButtonElement>("[data-slot='field-action']")!;
		expect(button.getAttribute("aria-label")).toBe("Call");
		const click = new MouseEvent("click", { bubbles: true, cancelable: true });
		button.dispatchEvent(click);
		expect(run).toHaveBeenCalledOnce();
		expect(onRowClick).not.toHaveBeenCalled();
		expect(click.defaultPrevented).toBe(true);
	});

	it("draws no button for an empty cell or when no app declares an action", async () => {
		expect((await mount("", [action()])).querySelector("button")).toBeNull();
		expect((await mount("123", [])).querySelector("button")).toBeNull();
	});
});
