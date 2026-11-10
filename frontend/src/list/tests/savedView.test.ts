// A return visit to a saved view's address paints from the last answer at once and asks again behind it.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick, type EffectScope } from "vue";

const runMethod = vi.hoisted(() => vi.fn());

vi.mock("@framework/ui/api", async (original) => ({
	isApiError: (await original<typeof import("@framework/ui/api")>()).isApiError,
	runMethod,
}));

import type { Session } from "@framework/ui/api";
import { setSession } from "@framework/ui/useSession";
import { resetSavedViews, useSavedView, type SavedView } from "../savedView";

const NOTES: SavedView = { key: "notes", label: "Notes", type: "Cards", layer: "app", applies: true };

const scopes: EffectScope[] = [];

beforeEach(() => {
	setUser("Administrator");
	runMethod.mockReset();
});

afterEach(() => {
	for (const scope of scopes.splice(0)) scope.stop();
	resetSavedViews();
});

function setUser(name: string) {
	setSession({ user: { name } } as unknown as Session);
}

/** Holds each `find` until the test answers it, in the order asked. */
function holdLookups() {
	const waiting: { resolve: (view: SavedView) => void; reject: (failure: unknown) => void }[] = [];
	runMethod.mockImplementation(
		() => new Promise((resolve, reject) => waiting.push({ resolve: (data) => resolve({ data }), reject }))
	);
	return async (answer: SavedView | Error) => {
		const next = waiting.shift()!;
		if (answer instanceof Error) next.reject(answer);
		else next.resolve(answer);
		await nextTick();
		await nextTick();
	};
}

function visit(doctype: string, key: string) {
	const scope = effectScope();
	scopes.push(scope);
	return scope.run(() => useSavedView(() => doctype, () => key))!;
}

describe("useSavedView on a return visit", () => {
	it("sets the view at once from the last answer, and asks again behind it", async () => {
		const answer = holdLookups();
		const first = visit("FCRM Note", "notes");
		expect(first.view.value).toBeNull();
		await answer(NOTES);
		scopes.pop()!.stop();

		const second = visit("FCRM Note", "notes");
		expect(second.view.value).toEqual(NOTES);
		expect(runMethod).toHaveBeenCalledTimes(2);

		const renamed = { ...NOTES, label: "My notes" };
		await answer(renamed);
		expect(second.view.value).toEqual(renamed);
	});

	it("shows nothing for a view not remembered for this doctype and key", async () => {
		const answer = holdLookups();
		visit("FCRM Note", "notes");
		await answer(NOTES);

		expect(visit("FCRM Note", "other").view.value).toBeNull();
		expect(visit("ToDo", "notes").view.value).toBeNull();
	});

	it("starts empty for another session user", async () => {
		const answer = holdLookups();
		visit("FCRM Note", "notes");
		await answer(NOTES);

		setUser("jane@example.com");
		expect(visit("FCRM Note", "notes").view.value).toBeNull();
	});

	it("does not keep an answer that lands after another session user took over", async () => {
		const answer = holdLookups();
		visit("FCRM Note", "notes");
		setUser("jane@example.com");
		visit("ToDo", "open");
		await answer(NOTES);

		expect(visit("FCRM Note", "notes").view.value).toBeNull();
	});

	it("clears the view and forgets it when the lookup is refused", async () => {
		const answer = holdLookups();
		visit("FCRM Note", "notes");
		await answer(NOTES);

		const second = visit("FCRM Note", "notes");
		expect(second.view.value).toEqual(NOTES);
		const refusal = new Error("gone");
		await answer(refusal);
		expect(second.view.value).toBeNull();
		expect(second.failure.value).toBe(refusal);

		expect(visit("FCRM Note", "notes").view.value).toBeNull();
	});
});
