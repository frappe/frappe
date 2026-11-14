// What an Act row does when it draws and when it is clicked, with the dispatcher and the palette stubbed.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, type EffectScope } from "vue";

const fake = vi.hoisted(() => ({
	find: vi.fn(),
	loads: vi.fn(),
	perform: vi.fn(),
	openArgumentStep: vi.fn(),
}));

vi.mock("@/acts/dispatcher", () => ({
	acts: { find: fake.find, loads: fake.loads, perform: fake.perform },
}));
vi.mock("@/shell/palette", () => ({ openArgumentStep: fake.openArgumentStep }));

import { isActAvailable, SPINNER_DELAY_MS, useActRow } from "../actRow";

let scope: EffectScope;

function row(rendering: { act: string; value?: unknown }) {
	return scope.run(() => useActRow(() => rendering))!;
}

beforeEach(() => {
	vi.useFakeTimers();
	scope = effectScope();
	fake.find.mockReturnValue({ name: "shell.theme" });
	fake.loads.mockReturnValue(false);
	fake.perform.mockResolvedValue(undefined);
});

afterEach(() => {
	scope.stop();
	vi.useRealTimers();
	vi.resetAllMocks();
});

describe("availability", () => {
	it("is hidden when no act answers to the name", () => {
		fake.find.mockReturnValue(undefined);
		expect(row({ act: "shell.gone" }).available.value).toBe(false);
	});

	it("is drawn while the app's acts are still loading", () => {
		fake.find.mockReturnValue(undefined);
		fake.loads.mockReturnValue(true);
		expect(isActAvailable("shell.crm.new_lead")).toBe(true);
	});
});

describe("a click", () => {
	it("performs the act with its preset", async () => {
		await row({ act: "shell.theme", value: "dark" }).run();
		expect(fake.perform).toHaveBeenCalledWith("shell.theme", "dark");
	});

	it("opens the argument step when the act has one and the row has no preset", async () => {
		fake.find.mockReturnValue({ argument: {} });
		await row({ act: "shell.create" }).run();

		expect(fake.openArgumentStep).toHaveBeenCalledWith("shell.create");
		expect(fake.perform).not.toHaveBeenCalled();
	});

	it("performs an act with no argument", async () => {
		await row({ act: "shell.theme" }).run();
		expect(fake.perform).toHaveBeenCalledWith("shell.theme", undefined);
	});

	it("performs a preset even when the act has an argument", async () => {
		fake.find.mockReturnValue({ argument: {} });
		await row({ act: "shell.create", value: "Note" }).run();
		expect(fake.perform).toHaveBeenCalledWith("shell.create", "Note");
	});
});

describe("the spinner", () => {
	function slowRun() {
		let settle!: () => void;
		fake.perform.mockReturnValue(new Promise<void>((resolve) => (settle = resolve)));
		return settle;
	}

	it("shows only after 300 ms, and stays until the run settles", async () => {
		const settle = slowRun();
		const act = row({ act: "shell.theme" });
		const running = act.run();

		vi.advanceTimersByTime(SPINNER_DELAY_MS - 1);
		expect(act.spinning.value).toBe(false);
		vi.advanceTimersByTime(1);
		expect(act.spinning.value).toBe(true);

		settle();
		await running;
		expect(act.spinning.value).toBe(false);
	});

	it("never shows for a quick act", async () => {
		const act = row({ act: "shell.theme" });
		await act.run();
		vi.advanceTimersByTime(SPINNER_DELAY_MS * 2);
		expect(act.spinning.value).toBe(false);
	});

	it("ignores a second click while the act runs", async () => {
		const settle = slowRun();
		const act = row({ act: "shell.theme" });
		const first = act.run();

		await act.run();
		expect(fake.perform).toHaveBeenCalledTimes(1);

		settle();
		await first;
	});
});
