// The comment writer's draft: what a reset clears, and an upload that lands after one.
import { afterEach, describe, expect, it, vi } from "vitest";
import { effectScope, nextTick } from "vue";

const { uploadCommentFile } = vi.hoisted(() => ({ uploadCommentFile: vi.fn() }));
vi.mock("../commentUpload", () => ({ uploadCommentFile }));

import { composerDraft, openComposer } from "@/shell/composer";
import { useCommentDraft } from "../useCommentDraft";

const FILE = {
	name: "F-1",
	file_name: "brief.pdf",
	file_url: "/private/files/brief.pdf",
	file_type: "application/pdf",
};
const MEDIA = { ...FILE, file_size: 10, is_private: 1 };

const scopes: ReturnType<typeof effectScope>[] = [];
let record = 0;

afterEach(() => {
	for (const scope of scopes.splice(0)) scope.stop();
	vi.clearAllMocks();
});

function draftOn(docname: string) {
	const scope = effectScope();
	scopes.push(scope);
	return scope.run(() => useCommentDraft("Note", docname))!;
}

function uploadLater() {
	let finish: () => void = () => {};
	uploadCommentFile.mockReturnValue(new Promise((resolve) => (finish = () => resolve(MEDIA))));
	return () => finish();
}

describe("the comment draft", () => {
	it("adds a file from the attach button to the stored draft", async () => {
		const docname = `NOTE-${++record}`;
		const draft = draftOn(docname);
		const finish = uploadLater();
		const uploaded = draft.upload(new File(["x"], "brief.pdf"));
		finish();
		await uploaded;
		await nextTick();
		expect(composerDraft("Note", docname, "comment")?.attachments).toEqual([
			{ ...FILE, file_size: 10 },
		]);
	});

	it("keeps a file out of the draft when a reset came while it uploaded", async () => {
		const docname = `NOTE-${++record}`;
		const draft = draftOn(docname);
		const finish = uploadLater();
		const uploaded = draft.upload(new File(["x"], "brief.pdf"));
		draft.content.value = "";
		finish();
		await uploaded;
		await nextTick();
		expect(draft.attachments.value).toEqual([]);
		expect(composerDraft("Note", docname, "comment")?.attachments).toEqual([]);
	});

	it("clears the files of a draft with no text on a reset, and can reset again", async () => {
		const docname = `NOTE-${++record}`;
		openComposer("Note", docname, "comment", { content: "", attachments: [FILE] });
		const draft = draftOn(docname);
		expect(draft.content.value).toBe("<p></p>");
		draft.content.value = "";
		await nextTick();
		expect(composerDraft("Note", docname, "comment")).toEqual({
			content: "<p></p>",
			attachments: [],
		});
		expect(draft.content.value).toBe("<p></p>");
	});
});
