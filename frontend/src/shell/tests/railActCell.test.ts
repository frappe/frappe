// The rail's Act cell: `SidebarRailItem`'s button form, so its tile is the route cells' tile.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, h, nextTick } from "vue";
import { DesktopShell } from "frappe-ui";

const mounted: ReturnType<typeof createApp>[] = [];
const act = vi.hoisted(() => ({ spinning: false, run: vi.fn() }));
vi.mock("../actRow", () => ({ useActRow: () => act }));

import RailActCell from "../RailActCell.vue";

afterEach(() => {
	mounted.splice(0).forEach((app) => app.unmount());
	document.body.innerHTML = "";
	act.run.mockClear();
	act.spinning = false;
});

function mount(props: { tile?: boolean } = {}, side = "left"): HTMLButtonElement {
	const host = document.body.appendChild(document.createElement("div"));
	const cell = () => h(RailActCell, { cell: { label: "Toggle theme", act: "shell.theme" }, ...props });
	const app = createApp({
		render: () => h(DesktopShell, { navSide: side as "left" | "right" }, { rail: cell }),
	});
	app.mount(host);
	mounted.push(app);
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
		expect(act.run).toHaveBeenCalledTimes(1);
	});

	it("is a plain tile on the phone's strip", () => {
		const button = mount({ tile: true });

		expect(button.getAttribute("data-slot")).toBeNull();
		expect(button.className).toContain("size-9");
		button.click();
		expect(act.run).toHaveBeenCalledTimes(1);
	});

	it.each([false, true])("marks itself busy while its act runs, in the rail and phone forms (tile %s)", (tile) => {
		expect(mount({ tile }).getAttribute("aria-busy")).toBe("false");
		mounted.splice(0).forEach((app) => app.unmount());
		act.spinning = true;
		const button = mount({ tile });

		expect(button.getAttribute("aria-busy")).toBe("true");
		expect(button.querySelector("[class*='size-4']")).not.toBeNull();
	});

	it.each([
		["left", "right"],
		["right", "left"],
	])("opens its tooltip away from a navigation on the %s", async (navSide, away) => {
		mount({}, navSide).dispatchEvent(new FocusEvent("focus"));
		await new Promise((resolve) => setTimeout(resolve, 50));
		await nextTick();

		expect(document.body.querySelector("[data-side]")?.getAttribute("data-side")).toBe(away);
	});
});
