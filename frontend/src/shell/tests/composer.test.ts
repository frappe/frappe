// The composer store: one open writer across records, and drafts kept per record and writer.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { isProxy } from "vue";
import { resetSession, setSession } from "@framework/ui/composables/useSession";
import type { Session } from "@framework/ui/api";
import {
	activeWriter,
	clearComposerDraft,
	closeComposer,
	composerDock,
	composerDraft,
	composerKept,
	composerRecord,
	composerRecordFor,
	composerState,
	composerUser,
	openComposer,
	preferredWindow,
	registerComposerDock,
	registerComposerRecord,
	saveComposerDraft,
	setComposerWindow,
	type WriterContext,
} from "../composer";

let record = 0;
let name = "";
let user = "";

beforeEach(() => {
	closeComposer();
	name = `NOTE-${++record}`;
	// A user per test: the remembered window outlives a test in the store as well as in storage.
	user = `reader-${record}@example.com`;
	signIn(user);
});

afterEach(() => {
	vi.unstubAllGlobals();
	resetSession();
	localStorage.clear();
});

function signIn(name: string) {
	const session = { user: { name }, roles: [], lang: "en", timezone: "UTC", defaults: {} };
	setSession(session as unknown as Session);
}

function context(docname: string, extra: Partial<WriterContext> = {}): WriterContext {
	return {
		doctype: "Note",
		docname,
		title: `Title of ${docname}`,
		perms: { write: 1 },
		toast: { error: () => {} },
		...extra,
	};
}

describe("composer store", () => {
	it("opens docked on one record and reads blank on any other", () => {
		openComposer("Note", name, "comment");
		expect(composerState).toMatchObject({
			doctype: "Note",
			name,
			active: "comment",
			window: "docked",
		});
		expect(activeWriter("Note", name)).toBe("comment");
		expect(activeWriter("Note", "OTHER")).toBe("");
		expect(activeWriter("Task", name)).toBe("");
	});

	it("collapses on close and keeps the draft", () => {
		openComposer("Note", name, "comment");
		saveComposerDraft("Note", name, "comment", {
			content: "<p>hi</p>",
			attachments: [],
		});
		closeComposer();
		expect(activeWriter("Note", name)).toBe("");
		expect(composerDraft("Note", name, "comment")).toEqual({
			content: "<p>hi</p>",
			attachments: [],
		});
	});

	it("seeds a draft only when none is in memory", () => {
		openComposer("Note", name, "comment", { content: "seed" });
		expect(composerDraft("Note", name, "comment")).toEqual({ content: "seed" });
		saveComposerDraft("Note", name, "comment", { content: "typed" });
		openComposer("Note", name, "comment", { content: "second seed" });
		expect(composerDraft("Note", name, "comment")).toEqual({
			content: "typed",
		});
	});

	it("keeps the first record's drafts when a second record takes the store", () => {
		saveComposerDraft("Note", name, "comment", { content: "first" });
		openComposer("Note", name, "comment");
		openComposer("Note", `${name}-B`, "comment");
		expect(activeWriter("Note", name)).toBe("");
		expect(activeWriter("Note", `${name}-B`)).toBe("comment");
		expect(composerDraft("Note", name, "comment")).toEqual({
			content: "first",
		});
	});

	it("keeps each writer's draft apart and clears one alone", () => {
		saveComposerDraft("Note", name, "comment", { content: "a" });
		saveComposerDraft("Note", name, "poll", { question: "b" });
		clearComposerDraft("Note", name, "comment");
		expect(composerDraft("Note", name, "comment")).toBeUndefined();
		expect(composerDraft("Note", name, "poll")).toEqual({ question: "b" });
	});

	it("never mixes up a name that holds the separator", () => {
		saveComposerDraft("Note", "a:b", "comment", { content: "x" });
		expect(composerDraft("Note:a", "b", "comment")).toBeUndefined();
	});
});

describe("the window", () => {
	it("opens docked for a reader who never chose", () => {
		openComposer("Note", name, "comment");
		expect(preferredWindow()).toBe("docked");
		expect(composerState.window).toBe("docked");
	});

	it("opens where the reader last put it, kept per user", () => {
		setComposerWindow("floating", { remember: true });
		expect(localStorage.getItem(`desk:composer-window:${user}`)).toBe("floating");
		openComposer("Note", name, "comment");
		expect(composerState.window).toBe("floating");

		signIn(`${user}-other`);
		expect(preferredWindow()).toBe("docked");
		openComposer("Note", name, "comment");
		expect(composerState.window).toBe("docked");
	});

	it("reads the choice from storage on a fresh session", () => {
		localStorage.setItem(`desk:composer-window:${user}`, "floating");
		expect(preferredWindow()).toBe("floating");
		localStorage.setItem(`desk:composer-window:${user}-b`, "sideways");
		expect(preferredWindow(`${user}-b`)).toBe("docked");
	});

	it("takes an open's window for that open only", () => {
		openComposer("Note", name, "comment", undefined, "floating");
		expect(composerState.window).toBe("floating");
		expect(preferredWindow()).toBe("docked");
		expect(localStorage.getItem(`desk:composer-window:${user}`)).toBeNull();

		openComposer("Note", name, "comment");
		expect(composerState.window).toBe("docked");
	});

	it("moves the open card without keeping the choice unless asked", () => {
		openComposer("Note", name, "comment");
		setComposerWindow("floating");
		expect(composerState.window).toBe("floating");
		expect(preferredWindow()).toBe("docked");
	});

	it("reads the choice from storage alone, so a cleared entry reads as the default", () => {
		setComposerWindow("floating", { remember: true });
		localStorage.removeItem(`desk:composer-window:${user}`);
		expect(preferredWindow()).toBe("docked");
	});

	it("takes the default when storage refuses the choice, and still moves the open card", () => {
		const refusing = {
			getItem: () => null,
			setItem: () => {
				throw new Error("QuotaExceededError");
			},
		};
		vi.stubGlobal("localStorage", refusing);
		openComposer("Note", name, "comment");
		setComposerWindow("floating", { remember: true });
		expect(composerState.window).toBe("floating");
		expect(preferredWindow()).toBe("docked");
	});

	it("keeps every choice under the session's user", () => {
		expect(composerUser()).toBe(user);
		setComposerWindow("floating", { remember: true });
		expect(preferredWindow(user)).toBe("floating");
	});

	it("gives a second record's open the window and keeps the first record's draft", () => {
		openComposer("Note", name, "comment", undefined, "floating");
		saveComposerDraft("Note", name, "comment", { content: "first" });
		openComposer("Note", `${name}-B`, "comment", undefined, "floating");

		expect(composerState).toMatchObject({ name: `${name}-B`, window: "floating" });
		expect(composerKept().title).toBe(`${name}-B`);
		expect(composerDraft("Note", name, "comment")).toEqual({ content: "first" });
	});
});

describe("the record's band and context", () => {
	it("gives the dock of the record the store is on, and none for another", () => {
		const band = document.createElement("div");
		const other = document.createElement("div");
		const unregister = registerComposerDock("Note", name, band);
		const unregisterOther = registerComposerDock("Note", `${name}-B`, other);

		openComposer("Note", name, "comment");
		expect(composerDock()).toBe(band);
		openComposer("Note", `${name}-C`, "comment");
		expect(composerDock()).toBeNull();

		unregisterOther();
		unregister();
		openComposer("Note", name, "comment");
		expect(composerDock()).toBeNull();
	});

	it("keeps a remount's dock when the old band unregisters after it", () => {
		const before = document.createElement("div");
		const after = document.createElement("div");
		const unregisterBefore = registerComposerDock("Note", name, before);
		const unregisterAfter = registerComposerDock("Note", name, after);
		unregisterBefore();

		openComposer("Note", name, "comment");
		expect(composerDock()).toBe(after);
		unregisterAfter();
	});

	it("gives the context of the record the store is on, and keeps its title and perms after", () => {
		const page = context(name);
		const unregister = registerComposerRecord("Note", name, page);
		openComposer("Note", name, "comment");
		expect(composerRecord()).toBe(page);
		expect(composerRecordFor("Note", name)).toBe(page);

		unregister();
		expect(composerRecord()).toBeNull();
		expect(composerRecordFor("Note", name)).toBeNull();
		expect(composerKept()).toEqual({ title: `Title of ${name}`, perms: { write: 1 } });
	});

	it("keeps the title the page last showed when it goes", () => {
		const page = { ...context(name), title: "Draft title" };
		const unregister = registerComposerRecord("Note", name, page);
		openComposer("Note", name, "comment");
		page.title = "Final title";
		unregister();
		expect(composerKept().title).toBe("Final title");
	});

	it("keeps what it had of a record through a reopen away from it", () => {
		const unregister = registerComposerRecord("Note", name, context(name, { perms: { email: 1 } }));
		openComposer("Note", name, "email");
		unregister();
		closeComposer();
		openComposer("Note", `${name}-B`, "comment");
		openComposer("Note", name, "email");
		expect(composerKept()).toEqual({ title: `Title of ${name}`, perms: { email: 1 } });
	});

	it("titles an open with the docname until the page registers", () => {
		openComposer("Note", name, "comment");
		expect(composerKept()).toEqual({ title: name, perms: {} });

		const unregister = registerComposerRecord("Note", name, context(name));
		expect(composerKept().title).toBe(`Title of ${name}`);
		unregister();
	});

	it("keeps the page's plain writers without their component or props", () => {
		const writers = [
			{ name: "comment", label: "Note", icon: "lucide-sticky-note", props: { size: 1 } },
			{ name: "poll", label: "Poll", component: { render: () => null } },
		];
		const unregister = registerComposerRecord("Note", name, context(name, { writers }));
		openComposer("Note", name, "comment");
		unregister();
		expect(composerKept().writers).toEqual([
			{ name: "comment", label: "Note", icon: "lucide-sticky-note" },
		]);
	});

	it("forgets a record whose page goes while the store is elsewhere and no draft waits", () => {
		registerComposerRecord("Note", name, context(name))();
		openComposer("Note", name, "comment");
		expect(composerKept().title).toBe(name);
	});

	it("keeps a record whose page goes while a draft waits, and forgets it with the last", () => {
		saveComposerDraft("Note", name, "comment", { content: "half" });
		saveComposerDraft("Note", name, "email", { subject: "half" });
		registerComposerRecord("Note", name, context(name))();
		clearComposerDraft("Note", name, "comment");
		openComposer("Note", name, "comment");
		expect(composerKept().title).toBe(`Title of ${name}`);

		openComposer("Note", `${name}-B`, "comment");
		clearComposerDraft("Note", name, "email");
		openComposer("Note", name, "comment");
		expect(composerKept().title).toBe(name);
	});

	it("keeps the record the store is on when its page goes and its draft clears", () => {
		const unregister = registerComposerRecord("Note", name, context(name));
		openComposer("Note", name, "comment");
		unregister();
		clearComposerDraft("Note", name, "comment");
		expect(composerKept().title).toBe(`Title of ${name}`);
	});

	it("never makes a registered context reactive", () => {
		const firePost = async () => {};
		const page = context(name, { firePost });
		const unregister = registerComposerRecord("Note", name, page);
		openComposer("Note", name, "comment");

		expect(composerRecord()).toBe(page);
		expect(isProxy(composerRecord())).toBe(false);
		expect(composerRecord()?.firePost).toBe(firePost);
		unregister();
	});
});
