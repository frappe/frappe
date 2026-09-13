import assert from "node:assert/strict"
import test from "node:test"

import {
	applyEvent,
	buildItems,
	codeRefLabel,
	compactDisplayText,
	conversationTitle,
	displayText,
	formatDuration,
	humanizeToolName,
	initialConversation,
	normalizeSkillCommand,
	parseSkillInvocation,
	skillCommand,
	splitCodeRefs,
	stepLiveLabel,
	userAttachments,
	userText,
} from "../src/transcript.js"

function toolGroups(conversation) {
	return buildItems(conversation).filter((item) => item.kind === "group")
}

test("a durable user message keeps the turn visibly working until it ends", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "Review this" })
	assert.equal(conversation.running, false)
	assert.equal(conversation.liveLabel, "Working")
	applyEvent(conversation, { type: "run_ended", seq: 3, reason: "done" })
	assert.equal(conversation.running, false)
	assert.equal(conversation.liveLabel, null)
})

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

test("code references appended by the composer split back out of the text", () => {
	const { body, refs } = splitCodeRefs("hi\n\n@src/flow_harness/agent/agent.py:10-15\n@/abs/config.py:17")
	assert.equal(body, "hi")
	assert.deepEqual(refs, [
		{ path: "src/flow_harness/agent/agent.py", start: 10, end: 15 },
		{ path: "/abs/config.py", start: 17, end: 17 },
	])
	assert.equal(codeRefLabel(refs[0]), "agent.py (10-15)")
	assert.equal(codeRefLabel(refs[1]), "config.py (17)")
	assert.deepEqual(splitCodeRefs("plain text"), { body: "plain text", refs: [] })
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

test("declarative tool displays drive live labels", () => {
	const display = [
		{ text: "Reading file " },
		{ text: "src/flow_harness/model/base.py", arg: "path" },
	]
	// the live line shortens read paths to the file name; the full path stays in displayText
	assert.equal(
		stepLiveLabel({ name: "read", arguments: { path: "src/flow_harness/model/base.py" }, display }),
		"Reading file base.py",
	)
	assert.equal(displayText(display), "Reading file src/flow_harness/model/base.py")
})

test("known tools retain generic fallbacks for older events", () => {
	assert.equal(
		stepLiveLabel({ name: "read", arguments: { path: "src/app.py" } }),
		"Reading file app.py",
	)
	assert.equal(stepLiveLabel({ name: "bash", arguments: { command: "git status" } }), "Running command")
	assert.equal(stepLiveLabel({ name: "grep", arguments: { pattern: "TODO" } }), "Searching code")
})

test("unknown tool names are humanized for future custom tools", () => {
	assert.equal(humanizeToolName("send_email_now"), "Send email now")
	assert.equal(humanizeToolName("create-calendar-event"), "Create calendar event")
	assert.equal(humanizeToolName("fetchAccountDetails"), "Fetch account details")
	assert.equal(stepLiveLabel({ name: "send_email_now", arguments: {} }), "Running send email now")
	assert.equal(
		stepLiveLabel({
			name: "web_search",
			arguments: { query: "Flow" },
			display: [{ text: "Searching the web for " }, { text: "Flow", arg: "query" }],
		}),
		"Searching the web for Flow",
	)
})

test("tool row argument text compacts paths for display", () => {
	const cwd = "/Users/dev/work/app"
	assert.equal(compactDisplayText("/Users/dev/work/app/src/main.py", cwd), "src/main.py")
	assert.equal(compactDisplayText("/Users/dev/work/app", cwd), ".")
	assert.equal(
		compactDisplayText("cd /Users/dev/work/app && git status", cwd),
		"git status",
	)
	assert.equal(
		compactDisplayText("grep -n x /Users/dev/work/app/src/a.py", cwd),
		"grep -n x src/a.py",
	)
	assert.equal(compactDisplayText("/Users/dev/other/file.py", cwd), "~/other/file.py")
	assert.equal(compactDisplayText("ls sites/", cwd), "ls sites/")
	assert.equal(compactDisplayText("src/main.py", null), "src/main.py")
})

test("live chat statuses do not use ellipses", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	assert.equal(conversation.liveLabel, "Working")
	// tool names never reach the status line — the row is the tool's only UI
	applyEvent(conversation, { type: "tool_call_started", name: "read" })
	assert.equal(conversation.liveLabel, "Working")
	applyEvent(conversation, {
		type: "tool_call_display_ready",
		id: "call-1",
		name: "read",
		arguments: { path: "src/events.py" },
		display: [{ text: "Inspecting " }, { text: "src/events.py", arg: "path" }],
	})
	assert.equal(conversation.liveLabel, "Working")
	assert.deepEqual(conversation.partial[0].display, [
		{ text: "Inspecting " },
		{ text: "src/events.py", arg: "path" },
	])
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
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read" })

	assert.deepEqual(conversation.partial, [
		{ type: "tool_call", id: "call-1", name: "read", arguments: null },
	])
	assert.deepEqual(toolGroups(conversation), [])
	assert.equal(conversation.liveLabel, "Working")
})

test("ready tool metadata creates one exact provisional step", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "edit" })
	applyEvent(conversation, {
		type: "tool_call_display_ready",
		id: "call-1",
		name: "edit",
		arguments: { path: "ui/App.vue" },
		display: [{ text: "Editing file " }, { text: "ui/App.vue", arg: "path" }],
	})
	applyEvent(conversation, {
		type: "tool_call_display_ready",
		id: "call-1",
		name: "edit",
		arguments: { path: "ui/Renamed.vue" },
		display: [{ text: "Editing file " }, { text: "ui/Renamed.vue", arg: "path" }],
	})

	assert.equal(conversation.partial.length, 1)
	assert.equal(conversation.liveLabel, "Working")
	const groups = toolGroups(conversation)
	assert.equal(groups.length, 1)
	assert.equal(groups[0].steps[0].call.arguments.path, "ui/Renamed.vue")
})

test("repeated identity-only tool starts never create ghost steps", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "write" })

	assert.deepEqual(conversation.partial, [
		{ type: "tool_call", id: "call-1", name: "write", arguments: null },
	])
	assert.deepEqual(toolGroups(conversation), [])
})

test("ready metadata preserves the provider order for parallel calls", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-2", name: "bash" })
	applyEvent(conversation, {
		type: "tool_call_display_ready",
		id: "call-2",
		name: "bash",
		arguments: { command: "pwd" },
	})
	applyEvent(conversation, {
		type: "tool_call_display_ready",
		id: "call-1",
		name: "read",
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
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read" })

	const durableCall = {
		type: "tool_call",
		id: "call-1",
		name: "read",
		arguments: { path: "src/flow_harness/events.py" },
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
		name: "read",
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

test("a preview replay replaces an existing provisional preview", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "text_delta", text: "prefix" })
	conversation.compacting = true
	conversation.liveLabel = "Compacting context"

	applyEvent(conversation, { type: "preview_replay_started" })
	assert.equal(conversation.compacting, true)
	assert.equal(conversation.liveLabel, "Compacting context")
	applyEvent(conversation, { type: "text_delta", text: "prefix" })
	applyEvent(conversation, { type: "text_delta", text: " suffix" })

	assert.deepEqual(conversation.partial, [{ type: "text", text: "prefix suffix" }])
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
	// its chunks are still arriving, so the thought row shimmers as "Thinking"
	assert.equal(steps[steps.length - 1].live, true)
	assert.ok(!buildItems(conversation).some((item) => item.kind === "thinking"))

	// a tool call after it ends the thought: the row settles to "Thought"
	applyEvent(conversation, { type: "tool_call_started", id: "call-2", name: "write" })
	const settled = toolGroups(conversation)[0].steps
	assert.equal(settled.findLast((step) => step.thought)?.live, false)
	assert.equal(conversation.liveLabel, "Working")
})

test("whitespace-only text between a thought and its tool call renders nothing", () => {
	const conversation = initialConversation()
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 1,
		content: [
			{ type: "thinking", thinking: "look at the file" },
			{ type: "text", text: "  " },
			{ type: "tool_call", id: "call-1", name: "read", arguments: { path: "sign.jpg" } },
		],
		stop_reason: "tool_use",
	})

	const items = buildItems(conversation)
	// the thought folds into the tool group instead of standing alone above an empty text item
	assert.deepEqual(items.map((item) => item.kind), ["group"])
	assert.deepEqual(items[0].steps[0].thought, { type: "thinking", thinking: "look at the file" })
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
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read" })
	assert.equal(buildItems(conversation).find((item) => item.kind === "thinking")?.block.thinking, "let me see")
	assert.deepEqual(toolGroups(conversation), [])

	// Complete live metadata arrives before execution and moves the thought into
	// the group with its filename available.
	applyEvent(conversation, {
		type: "tool_call_display_ready",
		id: "call-1",
		name: "read",
		arguments: { path: "src/app.js" },
		display: [{ text: "Reading file " }, { text: "src/app.js", arg: "path" }],
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
			{
				type: "tool_call",
				id: "call-1",
				name: "read",
				arguments: { path: "src/app.js" },
				display: [{ text: "Reading file " }, { text: "src/app.js", arg: "path" }],
			},
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
		type: "tool_call_display_ready",
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
			{ type: "tool_call", id: "call-1", name: "read", arguments: { path: "src/app.js" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, {
		type: "tool_result",
		seq: 4,
		ts: 107,
		tool_call_id: "call-1",
		name: "read",
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

test("a message in flight folds the turn before it, run_started or not", () => {
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
		{ type: "run_ended", seq: 3, ts: 13, reason: "done" },
	]) applyEvent(conversation, entry)
	const settled = buildItems(conversation).map((item) => item.kind)

	conversation.sending.push({
		key: "sending:1",
		entry: { type: "user_message", content: "Second", ts: 20 },
	})
	// the run starts before the server's copy of the message that started it
	applyEvent(conversation, { type: "run_started", seq: 4, ts: 20 })

	assert.deepEqual(buildItems(conversation).map((item) => item.kind), [...settled, "user"])
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

test("a denied tool call leaves a durable notice like an abort", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 10, content: "Change it" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 12,
		content: [{ type: "tool_call", id: "call-1", name: "write", arguments: { path: "src/app.js" } }],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, {
		type: "approval_required",
		seq: 4,
		ts: 12.1,
		calls: [{ id: "call-1", name: "write", args: { path: "src/app.js" } }],
	})
	applyEvent(conversation, { type: "run_ended", seq: 5, ts: 12.2, reason: "paused" })
	applyEvent(conversation, {
		type: "tool_result",
		seq: 6,
		ts: 14,
		tool_call_id: "call-1",
		content: '{"status": "denied", "message": "User denied this tool call."}',
		is_error: true,
	})
	applyEvent(conversation, { type: "run_ended", seq: 7, ts: 14.1, reason: "denied" })

	const items = buildItems(conversation)
	assert.ok(!items.some((item) => item.kind === "approval"))
	const notice = items.find((item) => item.kind === "notice")
	assert.equal(notice?.text, "Tool call denied by user")
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
		["text", "notice"],
	)
	assert.equal(buildItems(conversation)[0].block.text, "Partial answer")
})

test("a denied turn folds its narration with the work", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 10, content: "Create it" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 14,
		content: [
			{ type: "text", text: "Let me create it now." },
			{ type: "tool_call", id: "call-1", name: "write", arguments: { path: "hello.html" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, {
		type: "approval_required",
		seq: 4,
		ts: 14,
		calls: [{ id: "call-1", name: "write", args: { path: "hello.html" } }],
	})
	applyEvent(conversation, { type: "run_ended", seq: 5, ts: 14, reason: "paused" })
	applyEvent(conversation, { type: "run_started", seq: 6, ts: 17 })
	applyEvent(conversation, {
		type: "tool_result",
		seq: 7,
		ts: 17,
		tool_call_id: "call-1",
		content: '{"status": "denied", "message": "User denied this tool call."}',
		is_error: true,
	})
	applyEvent(conversation, { type: "run_ended", seq: 8, ts: 17, reason: "denied" })

	const collapsed = buildItems(conversation)
	assert.deepEqual(collapsed.map((item) => item.kind), ["user", "turn-fold", "notice"])
	assert.equal(collapsed[1].label, "Worked for 7s")

	const expanded = buildItems(conversation, new Set([collapsed[1].turnKey]))
	assert.deepEqual(expanded.map((item) => item.kind), ["user", "turn-fold", "text", "group", "notice"])
})

test("an aborted turn folds its partial response with the stopped work", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 30 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 30, content: "Do it" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 32,
		content: [
			{ type: "text", text: "I will run a command." },
			{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "echo hi" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, { type: "tool_result", seq: 4, ts: 33, tool_call_id: "call-1", content: "hi" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 5,
		ts: 36,
		content: [{ type: "text", text: "Partial resp" }],
		stop_reason: "aborted",
	})
	applyEvent(conversation, { type: "run_ended", seq: 6, ts: 36, reason: "aborted" })

	const collapsed = buildItems(conversation)
	assert.deepEqual(collapsed.map((item) => item.kind), ["user", "turn-fold", "notice"])
	assert.equal(collapsed[1].label, "You stopped after 6s")

	// expanding reveals the commentary, the tool group, and the aborted partial
	const expanded = buildItems(conversation, new Set([collapsed[1].turnKey]))
	assert.deepEqual(expanded.map((item) => item.kind), ["user", "turn-fold", "text", "group", "text", "notice"])
})

test("a started tool call takes the live status over from streamed thinking", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "planning the call" })

	let thinking = buildItems(conversation).find((item) => item.kind === "thinking")
	assert.equal(thinking.live, true)

	// the row renders only once arguments land; until then the thinking block
	// settles to "Thought" and the generic status line covers the wait
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "write" })
	thinking = buildItems(conversation).find((item) => item.kind === "thinking")
	assert.equal(thinking.live, false)
	assert.equal(conversation.liveLabel, "Working")
})

test("settled edit and write calls surface a changed-files section after the response", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 100 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 101, content: "Change it" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 102,
		content: [
			{ type: "tool_call", id: "e1", name: "edit", arguments: { path: "src/app.js" } },
			{ type: "tool_call", id: "w1", name: "write", arguments: { path: "src/new.js" } },
			{ type: "tool_call", id: "e2", name: "edit", arguments: { path: "src/app.js" } },
			{ type: "tool_call", id: "e3", name: "edit", arguments: { path: "src/bad.js" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, {
		type: "tool_result",
		seq: 4,
		tool_call_id: "e1",
		name: "edit",
		content: "[edited]",
		details: { path: "/proj/src/app.js", lines_added: 3, lines_removed: 1 },
	})
	applyEvent(conversation, {
		type: "tool_result",
		seq: 5,
		tool_call_id: "w1",
		name: "write",
		content: "[wrote]",
		details: { path: "/proj/src/new.js", lines: 12, chars: 100 },
	})
	// a second edit to the same file aggregates into one row
	applyEvent(conversation, {
		type: "tool_result",
		seq: 6,
		tool_call_id: "e2",
		name: "edit",
		content: "[edited]",
		details: { path: "/proj/src/app.js", lines_added: 2, lines_removed: 2 },
	})
	// failed calls never count as a change
	applyEvent(conversation, {
		type: "tool_result",
		seq: 7,
		tool_call_id: "e3",
		name: "edit",
		content: "[edit failed: no such file]",
		is_error: true,
		details: {},
	})
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 8,
		ts: 110,
		content: [{ type: "text", text: "Done." }],
		stop_reason: "stop",
	})
	applyEvent(conversation, { type: "run_ended", seq: 9, ts: 111, reason: "done" })

	const items = buildItems(conversation)
	assert.deepEqual(
		items.map((item) => item.kind),
		["user", "turn-fold", "text", "turn-files", "turn-copy"],
	)
	assert.deepEqual(items.find((item) => item.kind === "turn-files").files, [
		{ path: "/proj/src/app.js", added: 5, removed: 3 },
		{ path: "/proj/src/new.js", added: 12, removed: 0 },
	])
})

test("a running turn shows no changed-files section until the response settles", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 100 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 101, content: "Change it" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		ts: 102,
		content: [{ type: "tool_call", id: "e1", name: "edit", arguments: { path: "src/app.js" } }],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, {
		type: "tool_result",
		seq: 4,
		tool_call_id: "e1",
		name: "edit",
		content: "[edited]",
		details: { path: "/proj/src/app.js", lines_added: 1, lines_removed: 1 },
	})

	assert.ok(!buildItems(conversation).some((item) => item.kind === "turn-files"))
})
