import assert from "node:assert/strict"
import test from "node:test"

import {
	applyEvent,
	buildItems,
	conversationTitle,
	formatDuration,
	humanizeToolName,
	initialConversation,
	normalizeSkillCommand,
	parseSkillInvocation,
	skillCommand,
	stepLiveLabel,
	toolGroupLiveLabel,
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

test("expanded skill messages render compactly like Pi and Tau", () => {
	const expanded =
		'<skill name="security-review" location="/skills/security-review/SKILL.md">\n' +
		"References are relative to /skills/security-review.\n\n" +
		"large model-only instructions\n</skill>\n\ncheck this branch"
	const entry = {
		type: "user_message",
		content: expanded,
	}

	assert.equal(parseSkillInvocation(expanded).name, "security-review")
	assert.equal(userText(entry), "Using skill: security-review\ncheck this branch")
	assert.equal(skillCommand(entry), "/skill:security-review check this branch")
	assert.equal(conversationTitle({ entries: [entry] }), "check this branch")
	assert.equal(userText({ content: "ordinary" }), "ordinary")
	assert.equal(normalizeSkillCommand("/skill:security-review\n\ncheck this branch"), "/skill:security-review check this branch")
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

test("trivial thinking does not replace the latest meaningful tool status", () => {
	const finished = {
		call: { name: "read_file", arguments: { path: "src/flow/events.py" } },
		result: { content: "contents" },
	}
	assert.equal(toolGroupLiveLabel([finished], "Thinking"), "Working")
	assert.equal(toolGroupLiveLabel([finished], "Reading file events.py"), "Working")
	assert.equal(toolGroupLiveLabel([finished], "Retrying"), "Retrying")
	assert.equal(
		toolGroupLiveLabel(
			[
				finished,
				{ call: { name: "edit", arguments: { path: "ui/App.vue" } }, result: null },
			],
			"Thinking",
		),
		"Editing file App.vue",
	)
})

test("live chat statuses do not use ellipses", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	assert.equal(conversation.liveLabel, "Working")
	applyEvent(conversation, { type: "tool_call_started", name: "read_file" })
	assert.equal(conversation.liveLabel, "Working")
	applyEvent(conversation, {
		type: "tool_call_ready",
		id: "call-1",
		name: "read_file",
		arguments: { path: "src/events.py" },
	})
	assert.equal(conversation.liveLabel, "Reading file events.py")
	applyEvent(conversation, { type: "tool_call_started", name: "send_email_now" })
	assert.equal(conversation.liveLabel, "Working")
	applyEvent(conversation, { type: "retry", status: "scheduled" })
	assert.equal(conversation.liveLabel, "Retrying")
	applyEvent(conversation, { type: "compaction_started" })
	assert.equal(conversation.liveLabel, "Compacting context")
})

test("context window never carries across a model change", () => {
	const conversation = initialConversation()
	conversation.model = "codex/gpt-5.6-sol"
	conversation.contextWindow = 272_000
	conversation.contextTokens = 80_000

	applyEvent(conversation, { type: "model_changed", model: "deepseek/deepseek-chat" })
	assert.equal(conversation.contextWindow, null)
	assert.equal(conversation.contextTokens, 0)

	applyEvent(conversation, { type: "usage", context_window: 1_000_000 })
	assert.equal(conversation.contextWindow, 1_000_000)

	// Changing only reasoning effort keeps the selected model's known limit.
	applyEvent(conversation, {
		type: "model_changed",
		model: "deepseek/deepseek-chat",
		reasoning_effort: "high",
	})
	assert.equal(conversation.contextWindow, 1_000_000)
})

test("usage keeps cumulative spend separate from the current context", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "usage", input_tokens: 70_000, output_tokens: 1_000 })
	applyEvent(conversation, { type: "usage", input_tokens: 80_000, output_tokens: 2_000 })

	assert.equal(conversation.usage.input + conversation.usage.output, 153_000)
	assert.equal(conversation.contextTokens, 82_000)

	applyEvent(conversation, { type: "compaction", seq: 1, compact_up_to_seq: 0 })
	assert.equal(conversation.usage.input + conversation.usage.output, 153_000)
	assert.equal(conversation.contextTokens, 0)
})

test("identity-only tool starts stay hidden until actionable arguments arrive", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read_file" })

	assert.deepEqual(conversation.partial, [
		{ type: "tool_call", id: "call-1", name: "read_file", arguments: null },
	])
	assert.deepEqual(toolGroups(conversation), [])
	assert.equal(conversation.liveLabel, "Working")
})

test("ready tool metadata creates one exact provisional step", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "edit" })
	applyEvent(conversation, {
		type: "tool_call_ready",
		id: "call-1",
		name: "edit",
		arguments: { path: "ui/App.vue" },
	})
	applyEvent(conversation, {
		type: "tool_call_ready",
		id: "call-1",
		name: "edit",
		arguments: { path: "ui/Renamed.vue" },
	})

	assert.equal(conversation.partial.length, 1)
	assert.equal(conversation.liveLabel, "Editing file Renamed.vue")
	const groups = toolGroups(conversation)
	assert.equal(groups.length, 1)
	assert.equal(groups[0].steps[0].call.arguments.path, "ui/Renamed.vue")
})

test("repeated identity-only tool starts never create ghost steps", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read_file" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "write" })

	assert.deepEqual(conversation.partial, [
		{ type: "tool_call", id: "call-1", name: "write", arguments: null },
	])
	assert.deepEqual(toolGroups(conversation), [])
})

test("ready metadata preserves the provider order for parallel calls", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read_file" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-2", name: "bash" })
	applyEvent(conversation, {
		type: "tool_call_ready",
		id: "call-2",
		name: "bash",
		arguments: { command: "pwd" },
	})
	applyEvent(conversation, {
		type: "tool_call_ready",
		id: "call-1",
		name: "read_file",
		arguments: { path: "README.md" },
	})

	assert.deepEqual(
		toolGroups(conversation)[0].steps.map((step) => step.call.id),
		["call-1", "call-2"],
	)
})

test("durable assistant call creates the first visible step and receives the result", () => {
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
	assert.deepEqual(conversation.partial, [])

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

test("announced calls stay hidden and failed attempts leave no ghost steps", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "grep" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-2", name: "bash" })

	assert.deepEqual(toolGroups(conversation), [])

	applyEvent(conversation, { type: "retry", status: "started" })
	assert.deepEqual(conversation.partial, [])
	assert.deepEqual(toolGroups(conversation), [])
})

test("streamed thinking joins the trailing tool group's dropdown", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 1,
		content: [{ type: "tool_call", id: "call-1", name: "grep", arguments: { pattern: "x" } }],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, { type: "tool_result", seq: 2, tool_call_id: "call-1", name: "grep", content: "hit" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "next I should" })

	assert.equal(conversation.liveLabel, "Thinking")
	const steps = toolGroups(conversation)[0].steps
	assert.deepEqual(steps[steps.length - 1].thought, { type: "thinking", thinking: "next I should" })
	assert.ok(!buildItems(conversation).some((item) => item.kind === "thinking"))
})

test("streamed thinking stays visible until the actionable tool call arrives", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "user_message", seq: 1, content: "hi" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "let me see" })

	const live = buildItems(conversation).find((item) => item.kind === "thinking")
	assert.ok(live?.live)
	assert.equal(live.block.thinking, "let me see")

	// Identity alone does not hide the thought or announce a metadata-free tool.
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read_file" })
	assert.equal(buildItems(conversation).find((item) => item.kind === "thinking")?.block.thinking, "let me see")
	assert.deepEqual(toolGroups(conversation), [])

	// Complete live metadata arrives before execution and moves the thought into
	// the group with its filename available.
	applyEvent(conversation, {
		type: "tool_call_ready",
		id: "call-1",
		name: "read_file",
		arguments: { path: "src/app.js" },
	})
	assert.ok(!buildItems(conversation).some((item) => item.kind === "thinking"))
	let steps = toolGroups(conversation)[0].steps
	assert.deepEqual(steps.map((step) => step.thought?.thinking ?? step.call?.id), ["let me see", "call-1"])
	assert.equal(stepLiveLabel(steps[1].call), "Reading file app.js")

	// The durable call atomically replaces the provisional copy without duplicating it.
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 2,
		content: [
			{ type: "thinking", thinking: "let me see" },
			{ type: "tool_call", id: "call-1", name: "read_file", arguments: { path: "src/app.js" } },
		],
		stop_reason: "tool_use",
	})
	assert.ok(!buildItems(conversation).some((item) => item.kind === "thinking"))
	steps = toolGroups(conversation)[0].steps
	assert.deepEqual(steps.map((step) => step.thought?.thinking ?? step.call?.id), ["let me see", "call-1"])
	assert.equal(stepLiveLabel(steps[1].call), "Reading file app.js")
})

test("streamed thought, text, and tool call keep their order until the durable message", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "user_message", seq: 1, content: "understand the project" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "I should inspect the repository." })
	applyEvent(conversation, {
		type: "text_delta",
		text: "I'll explore the project structure to understand it thoroughly.",
	})
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "bash" })

	assert.deepEqual(conversation.partial.map((block) => block.type), ["thinking", "text", "tool_call"])
	assert.equal(conversation.liveLabel, "Working")
	const liveItems = buildItems(conversation)
	assert.deepEqual(liveItems.map((item) => item.kind), ["user", "thinking", "text"])
	assert.equal(liveItems[1].live, false)
	assert.equal(liveItems[1].block.thinking, "I should inspect the repository.")
	assert.equal(liveItems[2].block.text, "I'll explore the project structure to understand it thoroughly.")

	applyEvent(conversation, {
		type: "tool_call_ready",
		id: "call-1",
		name: "bash",
		arguments: { command: "ls" },
	})
	assert.deepEqual(conversation.partial.map((block) => block.type), ["thinking", "text", "tool_call"])
	assert.deepEqual(buildItems(conversation).map((item) => item.kind), ["user", "thinking", "text", "group"])

	applyEvent(conversation, {
		type: "assistant_message",
		seq: 2,
		content: [
			{ type: "thinking", thinking: "I should inspect the repository." },
			{ type: "text", text: "I'll explore the project structure to understand it thoroughly." },
			{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "ls" } },
		],
		stop_reason: "tool_use",
	})

	assert.deepEqual(conversation.partial, [])
	const durableItems = buildItems(conversation)
	assert.deepEqual(durableItems.map((item) => item.kind), ["user", "thinking", "text", "group"])
	assert.equal(durableItems.filter((item) => item.kind === "group").length, 1)
	assert.equal(durableItems[3].key, "g:call-1")
})

test("duration formatting matches compact t3code-style buckets", () => {
	assert.equal(formatDuration(350), "350ms")
	assert.equal(formatDuration(2_440), "2s")
	assert.equal(formatDuration(21_600), "22s")
	assert.equal(formatDuration(125_000), "2m 5s")
})

test("settled turns collapse intermediate work and preserve the final response", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 100 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 101, content: "Fix it" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 103,
		content: [
			{ type: "thinking", thinking: "I should inspect it." },
			{ type: "text", text: "I'll inspect the implementation." },
			{ type: "tool_call", id: "call-1", name: "read_file", arguments: { path: "src/app.js" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, {
		type: "tool_result",
		seq: 4,
		ts: 107,
		tool_call_id: "call-1",
		name: "read_file",
		content: "contents",
	})
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 5,
		ts: 113,
		content: [{ type: "text", text: "Fixed the implementation." }],
		stop_reason: "stop",
	})
	applyEvent(conversation, { type: "run_ended", seq: 6, ts: 113.4, reason: "done" })

	const collapsed = buildItems(conversation)
	assert.deepEqual(collapsed.map((item) => item.kind), ["user", "turn-fold", "text", "turn-copy"])
	assert.equal(collapsed[1].label, "Worked for 12s")
	assert.equal(collapsed[2].block.text, "Fixed the implementation.")
	assert.equal(collapsed[3].text, "Fixed the implementation.")

	const expanded = buildItems(conversation, new Set([collapsed[1].turnKey]))
	assert.deepEqual(expanded.map((item) => item.kind), [
		"user",
		"turn-fold",
		"thinking",
		"text",
		"group",
		"text",
		"turn-copy",
	])
	assert.equal(expanded[1].expanded, true)
	assert.equal(expanded[2].block.thinking, "I should inspect it.")
	assert.equal(expanded[3].block.text, "I'll inspect the implementation.")
	assert.equal(expanded[4].steps[0].call.id, "call-1")
})

test("the active turn never folds while previous settled turns remain collapsed", () => {
	const conversation = initialConversation()
	for (const entry of [
		{ type: "user_message", seq: 1, ts: 10, content: "First" },
		{
			type: "assistant_message",
			seq: 2,
			ts: 12,
			content: [
				{ type: "thinking", thinking: "First thought" },
				{ type: "text", text: "First answer" },
			],
			stop_reason: "stop",
		},
	]) applyEvent(conversation, entry)
	applyEvent(conversation, { type: "run_started", seq: 3, ts: 20 })
	applyEvent(conversation, { type: "user_message", seq: 4, ts: 20, content: "Second" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "Still working" })

	const items = buildItems(conversation)
	assert.deepEqual(items.map((item) => item.kind), [
		"user",
		"turn-fold",
		"text",
		"turn-copy",
		"user",
		"thinking",
	])
	assert.equal(items.at(-1).live, true)
})

test("a paused approval turn stays fully visible until the user resolves it", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 10, content: "Change it" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 12,
		content: [
			{ type: "thinking", thinking: "This needs approval." },
			{ type: "tool_call", id: "call-1", name: "write", arguments: { path: "src/app.js" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, {
		type: "approval_required",
		seq: 4,
		ts: 12.1,
		calls: [{ id: "call-1", name: "write", args: { path: "src/app.js" } }],
	})
	applyEvent(conversation, { type: "run_ended", seq: 5, ts: 12.2, reason: "paused" })

	const items = buildItems(conversation)
	assert.ok(!items.some((item) => item.kind === "turn-fold"))
	assert.ok(items.some((item) => item.kind === "thinking"))
	assert.ok(items.some((item) => item.kind === "approval"))
})

test("settled work without timestamps falls back to a plain Worked label", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 1, content: "Inspect" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 2,
		content: [
			{ type: "thinking", thinking: "Inspecting" },
			{ type: "text", text: "Done" },
		],
		stop_reason: "stop",
	})

	assert.equal(buildItems(conversation).find((item) => item.kind === "turn-fold")?.label, "Worked")
})

test("interrupted turns use t3code's stopped-duration label", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 30 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 31, content: "Start" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 35,
		content: [{ type: "thinking", thinking: "Working" }],
		stop_reason: "aborted",
	})
	applyEvent(conversation, { type: "run_ended", seq: 4, ts: 36, reason: "aborted" })

	const items = buildItems(conversation)
	assert.equal(items.find((item) => item.kind === "turn-fold")?.label, "You stopped after 5s")
	assert.ok(items.some((item) => item.kind === "notice"))
})

test("aborted response keeps its partial assistant content", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "text_delta", text: "Partial answer" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 1,
		content: [{ type: "text", text: "Partial answer" }],
		stop_reason: "aborted",
	})
	applyEvent(conversation, { type: "run_ended", seq: 2, reason: "aborted" })

	assert.deepEqual(
		buildItems(conversation).map((item) => item.kind),
		["text", "turn-copy", "notice"],
	)
	assert.equal(buildItems(conversation)[0].block.text, "Partial answer")
})
