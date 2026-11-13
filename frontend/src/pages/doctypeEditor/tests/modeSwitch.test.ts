import { describe, expect, it, vi } from "vitest";
import { confirmModeSwitch, type ModeSwitchAnswer } from "../modeSwitch";

function prompt(answer: ModeSwitchAnswer, { dirty = true, saves = true } = {}) {
	const ask = vi.fn(async () => answer);
	const save = vi.fn(async () => saves);
	return { ask, save, switches: () => confirmModeSwitch({ dirty, ask, save }) };
}

describe("the Design | Customize switch with pending edits", () => {
	it("switches at once when nothing is pending", async () => {
		const { ask, switches } = prompt(null, { dirty: false });
		expect(await switches()).toBe(true);
		expect(ask).not.toHaveBeenCalled();
	});

	it("saves first, then switches", async () => {
		const { save, switches } = prompt("save");
		expect(await switches()).toBe(true);
		expect(save).toHaveBeenCalledOnce();
	});

	it("stays when the save does not go through", async () => {
		const { switches } = prompt("save", { saves: false });
		expect(await switches()).toBe(false);
	});

	it("discards and switches without saving", async () => {
		const { save, switches } = prompt("discard");
		expect(await switches()).toBe(true);
		expect(save).not.toHaveBeenCalled();
	});

	it("stays on Cancel", async () => {
		const { save, switches } = prompt(null);
		expect(await switches()).toBe(false);
		expect(save).not.toHaveBeenCalled();
	});
});
