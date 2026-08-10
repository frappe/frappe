import assert from "node:assert/strict"
import test from "node:test"

import {
	applyEvent,
	buildItems,
	humanizeToolName,
	initialConversation,
	stepLiveLabel,
	toolGroupSummary,
	userAttachments,
	userText,
} from "../src/transcript.js"

function toolGroups(conversation) {
	return buildItems(conversation).filter((item) => item.kind === "group")
}

test("user content helpers support durable attachment blocks", () => {
	const entry = {
		content: [
			{ type: "text", text: "review this" },
			{ type: "attachment", id: "a", name: "screen.png", kind: "image" },
		],
	}
	assert.equal(userText(entry), "review this")
	assert.deepEqual(userAttachments(entry).map((item) => item.name), ["screen.png"])
	assert.equal(userText({ content: "legacy" }), "legacy")
})

test("live file-tool labels use only the filename", () => {
	assert.equal(
		stepLiveLabel({ name: "read_file", arguments: { path: "src/flow/model/base.py" } }),
		"Reading file base.py",
	)
	assert.equal(
		stepLiveLabel({ name: "write", arguments: { path: "docs/plan.md" } }),
		"Writing file plan.md",
	)
	assert.equal(
		stepLiveLabel({ name: "edit", arguments: { path: "src\\flow\\events.py" } }),
		"Editing file events.py",
	)
})

test("bash and grep labels stay generic", () => {
	assert.equal(stepLiveLabel({ name: "bash", arguments: { command: "git status" } }), "Running command")
	assert.equal(stepLiveLabel({ name: "grep", arguments: { pattern: "TODO" } }), "Searching code")
})

test("unknown tool names are humanized for future custom tools", () => {
	assert.equal(humanizeToolName("send_email_now"), "Send email now")
	assert.equal(humanizeToolName("create-calendar-event"), "Create calendar event")
	assert.equal(humanizeToolName("fetchAccountDetails"), "Fetch account details")
	assert.equal(stepLiveLabel({ name: "send_email_now", arguments: {} }), "Running send email now")
})

test("completed tool groups summarize unique activity kinds in order", () => {
	assert.equal(
		toolGroupSummary([
			{ name: "edit" },
			{ name: "write" },
			{ name: "bash" },
			{ name: "bash" },
		]),
		"Edited files, ran commands",
	)
	assert.equal(
		toolGroupSummary([{ name: "read_file" }, { name: "grep" }, { name: "send_email_now" }]),
		"Read file, searched code, used send email now",
	)
})

test("live chat statuses do not use ellipses", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	assert.equal(conversation.liveLabel, "Thinking")
	applyEvent(conversation, { type: "tool_call_started", name: "read_file" })
	assert.equal(conversation.liveLabel, "Reading file")
	applyEvent(conversation, { type: "tool_call_started", name: "send_email_now" })
	assert.equal(conversation.liveLabel, "Running send email now")
	applyEvent(conversation, { type: "retry", status: "scheduled" })
	assert.equal(conversation.liveLabel, "Retrying")
	applyEvent(conversation, { type: "compaction_started" })
	assert.equal(conversation.liveLabel, "Compacting context")
})

test("tool start immediately creates a provisional tool step", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read_file" })

	const groups = toolGroups(conversation)
	assert.equal(groups.length, 1)
	assert.equal(groups[0].key, "g:call-1")
	assert.deepEqual(groups[0].steps, [
		{
			call: { type: "tool_call", id: "call-1", name: "read_file", arguments: {} },
			result: null,
			aborted: false,
		},
	])
})

test("duplicate tool starts update one provisional step", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read_file" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "write" })

	assert.equal(conversation.liveToolCalls.length, 1)
	assert.equal(toolGroups(conversation)[0].steps[0].call.name, "write")
})

test("durable assistant call replaces its provisional step and receives the result", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read_file" })

	const durableCall = {
		type: "tool_call",
		id: "call-1",
		name: "read_file",
		arguments: { path: "src/flow/events.py" },
	}
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 1,
		content: [durableCall],
		stop_reason: "tool_use",
	})
	assert.deepEqual(conversation.liveToolCalls, [])

	applyEvent(conversation, {
		type: "tool_result",
		seq: 2,
		tool_call_id: "call-1",
		name: "read_file",
		content: "contents",
	})

	const groups = toolGroups(conversation)
	assert.equal(groups.length, 1)
	assert.equal(groups[0].key, "g:call-1")
	assert.equal(groups[0].steps.length, 1)
	assert.strictEqual(groups[0].steps[0].call, durableCall)
	assert.equal(groups[0].steps[0].result.content, "contents")
})

test("multiple announced calls keep their order and failed attempts leave no ghost steps", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "grep" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-2", name: "bash" })

	assert.deepEqual(
		toolGroups(conversation)[0].steps.map((step) => step.call.id),
		["call-1", "call-2"],
	)

	applyEvent(conversation, { type: "retry", status: "started" })
	assert.deepEqual(conversation.liveToolCalls, [])
	assert.deepEqual(toolGroups(conversation), [])
})
