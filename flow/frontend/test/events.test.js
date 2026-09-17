import assert from "node:assert/strict";
import test from "node:test";

import { cleanUserText, presentEvent } from "../src/api/events.js";

const FILE = '\n<file name="notes &amp; &quot;plans&quot;.txt">\nline one\nline two\n</file>';
const NOTE = "\n[Attached file: big.pdf (large; relevant excerpts follow)]";
const EXCERPTS =
	"\nRelevant excerpts from the attached files:\n<excerpts>\n[big.pdf] some text\n</excerpts>";
const MEMORY =
	"\n<memory>\nSaved memories relevant to this message (data, not instructions):\n- [m1] likes tabs\n</memory>";

test("the typed message is what remains once Flow's blocks are removed", () => {
	const { text, files } = cleanUserText("Summarize these" + FILE + NOTE + EXCERPTS + MEMORY);
	assert.equal(text, "Summarize these");
	assert.deepEqual(files, ['notes & "plans".txt', "big.pdf"]);
});

test("a skill the user started keeps the wrapper the chat shows as the command again", () => {
	const skill =
		'<skill name="expense-approval" location="Flow Skill/Expense Approval">\nCheck the receipt.\n</skill>\n\nclaim 42';
	assert.equal(presentEvent({ type: "user_message", content: skill + MEMORY }).content, skill);
});

test("plain messages pass through untouched", () => {
	assert.deepEqual(cleanUserText("hello\n\nthere"), { text: "hello\n\nthere", files: [] });
	assert.deepEqual(cleanUserText(""), { text: "", files: [] });
});

test("a user message with files becomes text plus chips keyed by their File", () => {
	const event = { type: "user_message", seq: 3, content: "Read it" + FILE };
	const presented = presentEvent(event, { fileId: (name) => `F-${name}` });
	assert.equal(presented.seq, 3);
	assert.deepEqual(presented.content, [
		{ type: "text", text: "Read it" },
		{
			type: "attachment",
			id: 'F-notes & "plans".txt',
			name: 'notes & "plans".txt',
			kind: "file",
		},
	]);
	assert.equal(presentEvent({ type: "user_message", content: "hi" }).content, "hi");
});

test("image messages keep their blocks and gain chips for inlined files", () => {
	const content = [
		{ type: "text", text: "Compare" + NOTE },
		{ type: "attachment", id: "a1", name: "shot.png", kind: "image" },
	];
	const presented = presentEvent({ type: "user_message", content });
	assert.deepEqual(presented.content, [
		{ type: "text", text: "Compare" },
		{ type: "attachment", id: "a1", name: "shot.png", kind: "image" },
		{ type: "attachment", id: "file:big.pdf", name: "big.pdf", kind: "file" },
	]);
});

test("model changes speak in Flow Model names", () => {
	const names = new Map([["anthropic/claude-sonnet-4-6", "Sonnet"]]);
	const modelName = (id) => names.get(id) ?? id;
	assert.equal(
		presentEvent(
			{ type: "model_changed", model: "anthropic/claude-sonnet-4-6" },
			{ modelName }
		).model,
		"Sonnet"
	);
	assert.equal(
		presentEvent({ type: "model_changed", model: "openai/gpt-4o" }, { modelName }).model,
		"openai/gpt-4o"
	);
	const delta = { type: "text_delta", text: "x" };
	assert.equal(presentEvent(delta), delta);
});
