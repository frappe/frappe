// `window.desk.acts.run` and `wait`: a confirm that opens ends the call early; the person's answer ends it for good.
import { afterEach, describe, expect, it, vi } from "vitest";
import { dialog as frappeDialog } from "frappe-ui";

vi.mock("frappe-ui", () => ({
	dialog: { confirm: vi.fn(() => ({ close: vi.fn() })), danger: vi.fn(() => ({ close: vi.fn() })) },
	toast: { success: vi.fn(), error: vi.fn() },
}));
vi.mock("@framework/ui/api", () => ({ getTranslations: vi.fn() }));

import { acts, ActDeclined, type ActScope } from "@/acts/dispatcher";
import { shellDialog } from "../dialog";
import { run, wait } from "../windowDesk/runs";

let release: (() => void) | undefined;

function register(items: Record<string, () => unknown>) {
	const surfaces = { test: () => Object.entries(items).map(([name, run]) => ({ item: { name, run }, hidden: false })) };
	release = acts.register({
		surfaces,
		context: () => null,
		passes: () => true,
		settled: () => undefined,
		hold: async (work: () => unknown) => work(),
		failed: () => {},
	} as unknown as ActScope);
}

async function confirmThen(result: unknown) {
	const asked = await shellDialog().confirm({ title: "Submit?", message: "Sure?" });
	if (!asked) throw new ActDeclined("test.submit");
	return result;
}

/** What the person does in the open dialog. */
function answer(yes: boolean) {
	const options = vi.mocked(frappeDialog.confirm).mock.lastCall![0] as { onConfirm?: () => unknown; onCancel?: () => unknown };
	return yes ? options.onConfirm?.() : options.onCancel?.();
}

afterEach(() => {
	release?.();
	vi.mocked(frappeDialog.confirm).mockClear();
});

describe("window.desk.acts.run", () => {
	it("resolves the act's result when no confirm opens", async () => {
		register({ plain: () => 4 });

		expect(await run("test.plain")).toMatchObject({ ok: true, data: 4 });
	});

	it("returns waiting_for_user with the dialog and a call id while a confirm is open", async () => {
		register({ submit: () => confirmThen(true) });

		const result = await run("test.submit");

		expect(result).toMatchObject({
			ok: false,
			error: { code: "waiting_for_user", call: expect.any(Number), dialog: { kind: "confirm", title: "Submit?" } },
		});
		await answer(true);
	});

	it("answers any other run with waiting_for_user while that confirm is open", async () => {
		register({ submit: () => confirmThen(true), plain: () => 4 });
		const first = await run("test.submit");

		const second = await run("test.plain");

		expect(second).toMatchObject({ ok: false, error: { code: "waiting_for_user", call: (first as any).error.call } });
		await answer(true);
		expect(await run("test.plain")).toMatchObject({ ok: true, data: 4 });
	});

	it("gives the final result through wait once the person confirms", async () => {
		register({ submit: () => confirmThen("done") });
		const { error } = (await run("test.submit")) as any;

		const ended = wait(error.call);
		await answer(true);

		expect(await ended).toMatchObject({ ok: true, data: "done", dialogs: [] });
	});

	it("counts a refused confirm as declined", async () => {
		register({ submit: () => confirmThen(true) });
		const { error } = (await run("test.submit")) as any;

		const ended = wait(error.call);
		await answer(false);

		expect(await ended).toMatchObject({ ok: false, error: { code: "declined" } });
	});

	it("keeps the result of a finished call for a late wait", async () => {
		register({ submit: () => confirmThen("late") });
		const { error } = (await run("test.submit")) as any;
		await answer(true);
		await vi.waitFor(async () => expect(await wait(error.call)).toMatchObject({ ok: true, data: "late" }));
	});
});

describe("window.desk.acts.wait", () => {
	it("returns waiting_for_user again when the timeout passes with the confirm open", async () => {
		register({ submit: () => confirmThen(true) });
		const { error } = (await run("test.submit")) as any;

		expect(await wait(error.call, { timeout: 10 })).toMatchObject({
			ok: false,
			error: { code: "waiting_for_user", call: error.call, dialog: { title: "Submit?" } },
		});
		await answer(true);
	});

	it("says `missing` for an id no run returned", async () => {
		expect(await wait(9999)).toMatchObject({ ok: false, error: { code: "missing" } });
	});
});

describe("which run a confirm belongs to", () => {
	function gate() {
		let open!: (value?: unknown) => void;
		const done = new Promise((resolve) => (open = resolve));
		return { done, open };
	}
	const settled = (promise: Promise<unknown>) => Promise.race([promise.then(() => true), new Promise((r) => setTimeout(r, 20, false))]);

	it("gives a confirm to the newest run and leaves an older pending run pending", async () => {
		const form = gate();
		register({ form: () => form.done, submit: () => confirmThen(true) });
		const older = run("test.form");

		const newer = (await run("test.submit")) as any;

		expect(newer.error).toMatchObject({ code: "waiting_for_user", dialog: { title: "Submit?" } });
		expect(await settled(older)).toBe(false);
		await answer(true);
		form.open("form done");
		expect(await older).toMatchObject({ ok: true, data: "form done" });
	});

	it("waits for a danger confirm like a confirm", async () => {
		register({
			remove: async () => {
				if (!(await shellDialog().danger({ title: "Delete?", message: "Sure?" }))) throw new ActDeclined("test.remove");
				return "gone";
			},
		});

		const result = (await run("test.remove")) as any;

		expect(result.error).toMatchObject({ code: "waiting_for_user", dialog: { kind: "danger", title: "Delete?" } });
		const options = vi.mocked(frappeDialog.danger).mock.lastCall![0] as { onConfirm?: () => unknown };
		await options.onConfirm?.();
		expect(await wait(result.error.call)).toMatchObject({ ok: true, data: "gone" });
	});

	it("lets other runs through once the parked call's own confirm is answered, though its act still runs", async () => {
		const slow = gate();
		register({ submit: async () => (await confirmThen(true), slow.done), plain: () => 4 });
		const { error } = (await run("test.submit")) as any;
		await answer(true);

		expect(await run("test.plain")).toMatchObject({ ok: true, data: 4 });
		expect(await wait(error.call, { timeout: 10 })).toMatchObject({
			ok: false,
			error: { code: "waiting_for_user", call: error.call, dialog: undefined },
		});
		slow.open("end");
		expect(await wait(error.call)).toMatchObject({ ok: true, data: "end" });
	});

	it("keeps holding other runs while the parked act opens a later confirm", async () => {
		register({
			twice: async () => {
				await confirmThen(true);
				return confirmThen("both");
			},
			plain: () => 4,
		});
		const { error } = (await run("test.twice")) as any;
		await answer(true);
		await vi.waitFor(() => expect(vi.mocked(frappeDialog.confirm)).toHaveBeenCalledTimes(2));

		expect(await run("test.plain")).toMatchObject({ ok: false, error: { code: "waiting_for_user", call: error.call } });
		await answer(true);
		expect(await wait(error.call)).toMatchObject({ ok: true, data: "both" });
	});

	it("gives a newer run's confirm to that run, not to an older parked act that still runs", async () => {
		const slow = gate();
		register({ first: async () => (await confirmThen(true), slow.done), second: () => confirmThen("two") });
		const { error: older } = (await run("test.first")) as any;
		await answer(true);

		const { error: newer } = (await run("test.second")) as any;

		expect(newer).toMatchObject({ code: "waiting_for_user", dialog: { title: "Submit?" } });
		expect(newer.call).not.toBe(older.call);
		await answer(true);
		slow.open("end");
	});

	it("hands a confirm back to the older act when the newer run that claimed it ends", async () => {
		const first = gate();
		const second = gate();
		register({
			older: async () => {
				await confirmThen(true);
				await first.done;
				return confirmThen("older");
			},
			newer: async () => (await second.done, "newer"),
			plain: () => 4,
		});
		const { error: older } = (await run("test.older")) as any;
		await answer(true);
		const newer = run("test.newer");
		first.open();
		const claimed = (await newer) as any;
		expect(claimed.error).toMatchObject({ code: "waiting_for_user", dialog: { title: "Submit?" } });

		second.open();
		await wait(claimed.error.call);

		expect(await run("test.plain")).toMatchObject({ ok: false, error: { code: "waiting_for_user", call: older.call } });
		await answer(true);
		expect(await wait(older.call)).toMatchObject({ ok: true, data: "older" });
	});
});
