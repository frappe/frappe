// The Act cell on the rail: its tooltip opens away from the navigation, on either side.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h } from "vue";

vi.mock("frappe-ui", async (importOriginal) => {
	const actual = await importOriginal<typeof import("frappe-ui")>();
	const Tooltip = defineComponent({
		props: ["side"],
		setup: (props, { slots }) => () => h("div", { "data-tooltip": props.side }, slots.default?.()),
	});
	return { ...actual, Tooltip };
});
vi.mock("../actRow", () => ({ useActRow: () => ({ spinning: false, run: vi.fn() }) }));

import RailActCell from "../RailActCell.vue";
import { navigationSide } from "../navigationSide";

afterEach(() => {
	document.body.innerHTML = "";
	navigationSide.value = "start";
});

function tooltipSide(): string | null {
	const host = document.body.appendChild(document.createElement("div"));
	createApp(RailActCell, { cell: { label: "Toggle theme", act: "shell.theme" } }).mount(host);
	return host.querySelector("[data-tooltip]")!.getAttribute("data-tooltip");
}

describe("the rail's Act cell", () => {
	it("opens its tooltip to the right of a left-hand navigation", () => {
		navigationSide.value = "start";
		expect(tooltipSide()).toBe("right");
	});

	it("opens its tooltip to the left of a right-hand navigation", () => {
		navigationSide.value = "end";
		expect(tooltipSide()).toBe("left");
	});
});
