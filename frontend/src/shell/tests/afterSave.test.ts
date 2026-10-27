// The after-save registry, and desk's own handlers: the person on screen and the reload toast.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { computed, reactive } from "vue";

const fake = vi.hoisted(() => ({ toast: vi.fn() }));
vi.mock("frappe-ui", () => ({ toast: fake.toast }));

import type { Session } from "@framework/ui/api";
import { registerAfterSave, runAfterSave, type SavedBinding } from "@/afterSave";
import { registerDeskAfterSave } from "../deskAfterSave";
import { registerAfterSave as appRegisterAfterSave } from "@/public";

const USER = "reader@example.com";

function saved(
	doctype: string,
	name: string,
	changed: string[],
	doc: Record<string, any> = {}
): SavedBinding {
	return { doctype, name, doc, changed };
}

describe("registerAfterSave", () => {
	it("runs each handler of the saved doctype, and none after it is removed", () => {
		const first = vi.fn();
		const second = vi.fn();
		const other = vi.fn();
		const removeFirst = registerAfterSave("Probe A", first);
		const removeSecond = registerAfterSave("Probe A", second);
		const removeOther = registerAfterSave("Probe B", other);

		runAfterSave(saved("Probe A", "one", ["x"]));
		removeFirst();
		runAfterSave(saved("Probe A", "one", ["x"]));
		removeSecond();
		removeOther();

		expect(first).toHaveBeenCalledTimes(1);
		expect(second).toHaveBeenCalledTimes(2);
		expect(other).not.toHaveBeenCalled();
	});

	it("logs a handler that throws and still runs the next", () => {
		const error = vi.spyOn(console, "error").mockImplementation(() => {});
		const next = vi.fn();
		const removeBroken = registerAfterSave("Probe C", () => {
			throw new Error("broken");
		});
		const removeNext = registerAfterSave("Probe C", next);

		runAfterSave(saved("Probe C", "one", ["x"]));
		removeBroken();
		removeNext();

		expect(next).toHaveBeenCalledTimes(1);
		expect(error).toHaveBeenCalledTimes(1);
		error.mockRestore();
	});

	it("is on the app import list (`@shell`), on the shell's own registry", () => {
		const run = vi.fn();
		const remove = appRegisterAfterSave("Probe D", run);

		runAfterSave(saved("Probe D", "Probe D", ["x"]));
		remove();

		expect(run).toHaveBeenCalledTimes(1);
	});
});

describe("desk's after-save handlers", () => {
	let session: Session;
	let unregister: () => void;

	beforeEach(() => {
		fake.toast.mockReset();
		session = {
			user: reactive({
				name: USER,
				full_name: "Ada",
				email: USER,
				user_image: null,
				document_follow_notify: false,
			}),
			roles: [],
			lang: "en",
			timezone: "Europe/Paris",
			defaults: {},
		};
		unregister = registerDeskAfterSave(session);
	});

	afterEach(() => unregister());

	it("shows the session user's new name, image and follow setting, with no toast", () => {
		const shown = computed(() => `${session.user.full_name} ${session.user.user_image}`);
		expect(shown.value).toBe("Ada null");

		runAfterSave(
			saved("User", USER, ["first_name", "user_image"], {
				full_name: "Ada Lovelace",
				user_image: "/files/ada.png",
				document_follow_notify: 1,
			})
		);

		expect(shown.value).toBe("Ada Lovelace /files/ada.png");
		expect(session.user.document_follow_notify).toBe(true);
		expect(fake.toast).not.toHaveBeenCalled();
	});

	it("leaves the session alone when another user's record saves", () => {
		runAfterSave(saved("User", "other@example.com", ["language"], { full_name: "Other" }));

		expect(session.user.full_name).toBe("Ada");
		expect(fake.toast).not.toHaveBeenCalled();
	});

	it("asks for a reload under one toast id when language or time zone changes", () => {
		runAfterSave(saved("User", USER, ["language"], { full_name: "Ada" }));
		runAfterSave(saved("User", USER, ["time_zone"], { full_name: "Ada" }));

		expect(fake.toast).toHaveBeenCalledTimes(2);
		const ids = fake.toast.mock.calls.map(([, options]) => options.id);
		expect(new Set(ids).size).toBe(1);
		const [message, options] = fake.toast.mock.calls[0];
		expect(message).toBe("Reload to apply");
		expect(options.action.label).toBe("Reload");
		expect(options.duration).toBe(Infinity);
	});

	it("asks for a reload when System Settings changes a format or the time zone, and not otherwise", () => {
		runAfterSave(
			saved("System Settings", "System Settings", ["country", "enable_onboarding"])
		);
		expect(fake.toast).not.toHaveBeenCalled();

		runAfterSave(saved("System Settings", "System Settings", ["date_format"]));
		expect(fake.toast).toHaveBeenCalledTimes(1);
	});
});
