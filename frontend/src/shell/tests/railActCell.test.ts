// The rail's Act cell: `SidebarRailItem`'s button form, so its tile is the route cells' tile.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp } from "vue";

const run = vi.fn();
vi.mock("../actRow", () => ({ useActRow: () => ({ spinning: false, run }) }));

import RailActCell from "../RailActCell.vue";

afterEach(() => {
	document.body.innerHTML = "";
	run.mockClear();
});

function mount(props: { tile?: boolean } = {}): HTMLButtonElement {
	const host = document.body.appendChild(document.createElement("div"));
	createApp(RailActCell, { cell: { label: "Toggle theme", act: "shell.theme" }, ...props }).mount(host);
	return host.querySelector("button")!;
}

describe("the rail's Act cell", () => {
	it("is frappe-ui's rail tile as a button, named by its label, and runs its act on click", () => {
		const button = mount();

		expect(button.getAttribute("data-slot")).toBe("sidebar-rail-item");
		expect(button.getAttribute("aria-label")).toBe("Toggle theme");
		expect(button.getAttribute("aria-current")).toBeNull();
		expect(button.className).toContain("rounded-[7px]");
		button.click();
		expect(run).toHaveBeenCalledTimes(1);
	});

	it("is a plain tile on the phone's strip", () => {
		const button = mount({ tile: true });

		expect(button.getAttribute("data-slot")).toBeNull();
		expect(button.className).toContain("size-9");
		button.click();
		expect(run).toHaveBeenCalledTimes(1);
	});
});
