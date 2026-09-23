// The composer store: one open writer across records, and drafts kept per record and writer.
import { beforeEach, describe, expect, it } from "vitest";
import {
	activeWriter,
	clearComposerDraft,
	closeComposer,
	composerDraft,
	composerState,
	openComposer,
	saveComposerDraft,
} from "../composer";

let record = 0;
let name = "";

beforeEach(() => {
	closeComposer();
	name = `NOTE-${++record}`;
});

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
