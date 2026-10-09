import assert from "node:assert/strict"
import test from "node:test"

import {
	applyEvent,
	approvalToAnswer,
	buildItems,
	buildTranscriptRows,
	codeRefLabel,
	compactDisplayText,
	conversationTitle,
	displayText,
	formatDuration,
	humanizeToolName,
	initialConversation,
	normalizeSkillCommand,
	parseSkillInvocation,
	quoteBlock,
	skillCommand,
	splitCodeRefs,
	splitQuotes,
	stepLiveLabel,
	stepStat,
	stepSubject,
	subagentId,
	subagentTitle,
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

test("quotes added to chat travel as blockquotes under the text and split back out", () => {
	assert.equal(quoteBlock("a\n\nb"), "> a\n>\n> b")
	assert.deepEqual(splitQuotes("hi\n\n> a\n>\n> b\n\n> c"), { body: "hi", quotes: ["a\n\nb", "c"] })
	assert.deepEqual(splitQuotes("> only"), { body: "", quotes: ["only"] })
	assert.deepEqual(splitQuotes("> top\n\nplain"), { body: "> top\n\nplain", quotes: [] })
	assert.deepEqual(splitQuotes("plain"), { body: "plain", quotes: [] })
})

test("expanded skill messages render as the command the user typed", () => {
	const expanded =
		'<skill name="security-review" location="/skills/security-review/SKILL.md">\n' +
		"References are relative to /skills/security-review.\n\n" +
		"large model-only instructions\n</skill>\n\ncheck this branch"
	const entry = {
		type: "user_message",
		content: expanded,
	}

	assert.equal(parseSkillInvocation(expanded).name, "security-review")
	assert.equal(userText(entry), "/skill:security-review check this branch")
	assert.equal(skillCommand(entry), "/skill:security-review check this branch")
	assert.equal(conversationTitle({ entries: [entry] }), "check this branch")
	const typed = { type: "user_message", content: [{ type: "text", text: "/skill:review fix the tests" }] }
	assert.equal(conversationTitle({ entries: [], sending: [{ entry: typed }] }), "fix the tests")
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

test("a steered message waits below the running turn without settling it", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "user_message", seq: 2, ts: 10, content: "First" })
	applyEvent(conversation, { type: "text_delta", text: "Looking into it" })
	const live = buildItems(conversation)

	conversation.steering.push({ key: "steering:1", entry: { type: "user_message", content: "Also this", ts: 11 } })
	const items = buildItems(conversation)
	assert.deepEqual(items.slice(0, -1), live)
	assert.deepEqual([items.at(-1).kind, items.at(-1).key], ["user", "steering:1"])
})

test("a steered message waits below the message still on its way, whose run it joins", () => {
	const conversation = initialConversation()
	conversation.sending.push({ key: "sending:1", entry: { type: "user_message", content: "Next", ts: 10 } })
	conversation.steering.push({ key: "steering:2", entry: { type: "user_message", content: "And this", ts: 11 } })
	assert.deepEqual(
		buildItems(conversation).map((item) => item.key),
		["sending:1", "steering:2"],
	)
})

test("a run that ends mid-compaction leaves no compaction behind", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started", seq: 1, ts: 10 })
	applyEvent(conversation, { type: "compaction_started", reason: "manual" })
	// the stream dropped compaction_ended, or the run was cut off before it
	applyEvent(conversation, { type: "run_ended", seq: 2, ts: 11, reason: "error" })
	assert.equal(conversation.compacting, false)
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

test("a thought keeps its id from the streamed preview through its merge into a tool group", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "user_message", seq: 1, content: "hi" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "let me see" })
	assert.equal(buildItems(conversation).find((item) => item.kind === "thinking").key, "turn:1:th:0")

	applyEvent(conversation, { type: "tool_call_display_ready", id: "call-1", name: "bash", arguments: { command: "ls" } })
	assert.equal(toolGroups(conversation)[0].steps[0].id, "turn:1:th:0")

	applyEvent(conversation, {
		type: "assistant_message",
		seq: 2,
		content: [
			{ type: "thinking", thinking: "let me see" },
			{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "ls" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, { type: "tool_result", seq: 3, tool_call_id: "call-1", content: "a.js" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "now write" })
	assert.deepEqual(
		toolGroups(conversation)[0].steps.map((step) => step.call?.id ?? step.id),
		["turn:1:th:0", "call-1", "turn:1:th:1"],
	)
})

test("a text-less thinking block in the durable message takes no thought ordinal", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "user_message", seq: 1, content: "hi" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "let me see" })
	applyEvent(conversation, { type: "tool_call_display_ready", id: "call-1", name: "bash", arguments: { command: "ls" } })
	assert.equal(toolGroups(conversation)[0].steps[0].id, "turn:1:th:0")

	// the redacted block never streamed; it lands only in the durable message
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 2,
		content: [
			{ type: "thinking", thinking: "", redacted: true },
			{ type: "thinking", thinking: "let me see" },
			{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "ls" } },
		],
		stop_reason: "tool_use",
	})
	assert.deepEqual(
		toolGroups(conversation)[0].steps.map((step) => step.call?.id ?? step.id),
		["th:2:0", "turn:1:th:0", "call-1"],
	)
})

test("a settled turn stays unfolded while one of its rows is open", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 1, ts: 100, content: "Fix it" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 2,
		ts: 101,
		content: [
			{ type: "thinking", thinking: "look first" },
			{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "ls" } },
		],
		stop_reason: "tool_use",
	})
	applyEvent(conversation, { type: "tool_result", seq: 3, ts: 102, tool_call_id: "call-1", content: "a.js" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 4,
		ts: 103,
		content: [{ type: "text", text: "Done." }],
		stop_reason: "stop",
	})
	applyEvent(conversation, { type: "run_ended", seq: 5, ts: 103, reason: "done" })

	assert.deepEqual(buildItems(conversation).map((item) => item.kind), ["user", "turn-fold", "text", "turn-copy"])
	for (const id of ["call-1", "turn:1:th:0"]) {
		const items = buildItems(conversation, new Set(), new Set([id]))
		assert.deepEqual(items.map((item) => item.kind), ["user", "turn-fold", "group", "text", "turn-copy"], id)
		assert.equal(items[1].expanded, true)
	}
	assert.equal(buildItems(conversation, new Set(), new Set(["call-9"]))[1].expanded, false)
})

function subagentTurn(conversation) {
	applyEvent(conversation, { type: "run_started", seq: 1, run_id: "r1" })
	applyEvent(conversation, { type: "user_message", seq: 2, content: "go" })
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 3,
		content: [{ type: "tool_call", id: "c1", name: "subagent", arguments: { task: "count", description: "count beans" } }],
	})
	applyEvent(conversation, { type: "run_started", seq: 4, run_id: "r2", subagent_id: "c1" })
	applyEvent(conversation, { type: "user_message", seq: 5, content: "count", subagent_id: "c1" })
	applyEvent(conversation, { type: "text_delta", text: "forty", subagent_id: "c1" })
}

test("a sub-agent's events fold into a thread of their own that its step carries", () => {
	const conversation = initialConversation()
	subagentTurn(conversation)
	const child = conversation.subagents.c1
	assert.equal(child.running, true)
	assert.deepEqual(child.partial, [{ type: "text", text: "forty" }])
	assert.equal(conversation.partial.length, 0) // the child's preview is not the session's
	assert.equal(conversation.entries.length, 2)
	assert.equal(subagentTitle(conversation, "c1"), "count beans")
	assert.equal(subagentTitle(conversation, "c9"), null)
	// a call still streaming already has a row to open, so it has a title too
	const live = initialConversation()
	applyEvent(live, { type: "tool_call_display_ready", id: "c2", name: "subagent", arguments: { description: "sort beans" } })
	assert.equal(subagentTitle(live, "c2"), "sort beans")

	let [step] = toolGroups(conversation)[0].steps
	assert.equal(step.subagent, child)
	assert.equal(subagentId(step.call), "c1")
	assert.equal(stepSubject(step.call), "count beans")

	applyEvent(conversation, { type: "assistant_message", seq: 6, content: [{ type: "text", text: "forty-two" }], subagent_id: "c1" })
	applyEvent(conversation, { type: "usage", seq: 7, input_tokens: 30, output_tokens: 9, cost: 0.5, subagent_id: "c1" })
	applyEvent(conversation, { type: "run_ended", seq: 8, reason: "done", subagent_id: "c1" })
	applyEvent(conversation, {
		type: "tool_result",
		seq: 9,
		tool_call_id: "c1",
		name: "subagent",
		content: "forty-two\n\n[subagent_id: c1]",
		details: { subagent_id: "c1", agent: "general", end_reason: "done" },
	})
	;[step] = toolGroups(conversation)[0].steps
	assert.equal(step.result.seq, 9)
	assert.equal(stepStat(step), "") // the default agent is not worth a stat
	assert.equal(child.running, false)
	assert.equal(child.entries.at(-1).subagent_id, "c1") // a child's row keeps its tag
	assert.equal(conversation.usage.output, 9) // the child's cost is the session's cost
	assert.equal(conversation.usage.cost, 0.5)
	assert.equal(conversation.contextTokens, 0) // its context is not
	assert.equal(conversation.latestSeq, 9)
	// the child's thread reads like the session's: its task, then its answer
	assert.deepEqual(buildItems(child).map((item) => item.kind), ["user", "text", "turn-copy"])

	// a continuation names the same child; a stopped child says why
	const again = { id: "c2", name: "subagent", arguments: { task: "again", description: "recount", subagent_id: "c1" } }
	assert.equal(subagentId(again), "c1")
	assert.equal(stepStat({ result: { details: { agent: "general", end_reason: "max_turns" } } }), "max turns")
	assert.equal(stepStat({ result: { details: { agent: "researcher", end_reason: "done" } } }), "researcher")
})

test("a sub-agent a crash cut off stops working when its session's run ends", () => {
	const conversation = initialConversation()
	subagentTurn(conversation)
	applyEvent(conversation, { type: "run_error", seq: 6, message: "The flow server stopped before this run ended." })
	applyEvent(conversation, { type: "run_ended", seq: 7, reason: "error" })
	const child = conversation.subagents.c1
	assert.deepEqual([child.running, child.liveLabel, child.partial], [false, null, []])
})

test("a sub-agent's question is the batch to answer while the session runs", () => {
	const conversation = initialConversation()
	subagentTurn(conversation)
	const calls = [{ id: "c2", name: "bash", args: { command: "rm x" } }]
	applyEvent(conversation, { type: "approval_required", seq: 6, calls, subagent_id: "c1" })
	applyEvent(conversation, { type: "run_ended", seq: 7, reason: "paused", subagent_id: "c1" })
	assert.equal(conversation.pendingApproval, null) // the session itself never paused
	assert.equal(conversation.running, true)
	assert.deepEqual(approvalToAnswer(conversation), { seq: 6, calls, answers: {}, subagentId: "c1" })
	assert.equal(buildItems(conversation.subagents.c1).some((item) => item.kind === "group"), false) // the gated call waits in the card

	// the answers reached the child
	applyEvent(conversation, { type: "run_started", seq: 8, run_id: "r3", subagent_id: "c1" })
	assert.equal(approvalToAnswer(conversation), null)

	// a cancelled batch drops its calls one result at a time
	applyEvent(conversation, { type: "approval_required", seq: 9, calls, subagent_id: "c1" })
	applyEvent(conversation, { type: "tool_result", seq: 10, tool_call_id: "c2", name: "bash", content: "{}", subagent_id: "c1" })
	assert.equal(approvalToAnswer(conversation), null)

	// several waiting children ask oldest first, and the session's run ending voids them all
	applyEvent(conversation, { type: "run_started", seq: 11, run_id: "r4", subagent_id: "c3" })
	applyEvent(conversation, { type: "approval_required", seq: 12, calls, subagent_id: "c3" })
	applyEvent(conversation, { type: "approval_required", seq: 13, calls, subagent_id: "c1" })
	assert.equal(approvalToAnswer(conversation).subagentId, "c3")
	applyEvent(conversation, { type: "run_ended", seq: 14, reason: "aborted" })
	assert.equal(approvalToAnswer(conversation), null)
})

// --- the transcript's per-request usage ----------------------------------

const usageEvent = (seq, input, output) => ({
	type: "usage",
	seq,
	input_tokens: input,
	output_tokens: output,
})

function repliedWith(conversation, seq, calls) {
	applyEvent(conversation, {
		type: "assistant_message",
		seq,
		content: [{ type: "text", text: "on it" }, ...calls.map((id) => ({ type: "tool_call", id, name: "read", arguments: { path: `${id}.py` } }))],
	})
}

test("the transcript opens with a stand-in for the system prompt, never its text", () => {
	const conversation = initialConversation()
	assert.deepEqual(buildTranscriptRows(conversation), [])
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	const [first] = buildTranscriptRows(conversation)
	assert.equal(first.kind, "system")
	assert.equal(first.body, "System prompt.")
})

test("the first request's input and output stay with its assistant response", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	repliedWith(conversation, 3, [])
	applyEvent(conversation, usageEvent(4, 1000, 10))

	const rows = buildTranscriptRows(conversation)
	assert.deepEqual(rows.map((row) => row.kind), ["system", "user", "assistant"])
	assert.equal(rows[1].usage, undefined)
	assert.equal(rows[2].usage.input_tokens, 1000)
	assert.equal(rows[2].usage.output_tokens, 10)
})

test("a tool result has no fabricated token count", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	repliedWith(conversation, 3, ["a"])
	applyEvent(conversation, usageEvent(4, 1000, 10))
	applyEvent(conversation, { type: "tool_result", seq: 5, tool_call_id: "a", name: "read", content: "x".repeat(400) })
	repliedWith(conversation, 6, [])
	applyEvent(conversation, usageEvent(7, 1200, 20))

	const rows = buildTranscriptRows(conversation)
	assert.equal(rows.find((row) => row.kind === "tool").usage, undefined)
	assert.deepEqual(rows.filter((row) => row.kind === "assistant").map((row) => row.usage.input_tokens), [1000, 1200])
})

test("parallel tool results stay separate from the next request's usage", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	repliedWith(conversation, 3, ["a", "b"])
	applyEvent(conversation, usageEvent(4, 1000, 10))
	applyEvent(conversation, { type: "tool_result", seq: 5, tool_call_id: "a", name: "read", content: "x".repeat(400) })
	applyEvent(conversation, { type: "tool_result", seq: 6, tool_call_id: "b", name: "read", content: "x".repeat(1200) })
	repliedWith(conversation, 7, [])
	applyEvent(conversation, usageEvent(8, 1410, 20))

	const rows = buildTranscriptRows(conversation)
	assert.deepEqual(rows.filter((row) => row.kind === "tool").map((row) => row.usage), [undefined, undefined])
	assert.equal(rows.filter((row) => row.kind === "assistant")[1].usage.input_tokens, 1410)
})

test("an aborted response without usage stays uncounted", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	repliedWith(conversation, 3, [])
	applyEvent(conversation, usageEvent(4, 1000, 10))
	applyEvent(conversation, { type: "assistant_message", seq: 5, content: [{ type: "text", text: "x".repeat(400) }], stop_reason: "aborted" })
	applyEvent(conversation, { type: "run_ended", seq: 6, reason: "aborted" })
	applyEvent(conversation, { type: "user_message", seq: 7, content: "again" })
	repliedWith(conversation, 8, [])
	applyEvent(conversation, usageEvent(9, 1200, 20))

	const rows = buildTranscriptRows(conversation)
	const aborted = rows.find((row) => row.key === "a:5")
	assert.equal(aborted.usage, undefined)
	assert.equal(rows.find((row) => row.key === "u:7").usage, undefined)
	assert.equal(rows.find((row) => row.key === "a:8").usage.input_tokens, 1200)
})

test("an aborted turn's empty usage report is not a model call", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "go" })
	applyEvent(conversation, { type: "assistant_message", seq: 3, content: [{ type: "text", text: "half a th" }], stop_reason: "aborted" })
	applyEvent(conversation, { type: "usage", seq: 4 }) // what the adapters yield on cancel

	assert.deepEqual(conversation.requests, [])
	assert.equal(buildTranscriptRows(conversation).find((row) => row.kind === "assistant").usage, undefined)
})

test("rows show each entry as sent, minus Flow's own fields", () => {
	const conversation = initialConversation()
	const logged = (seq) => ({ seq, parent_seq: seq - 1, ts: 1700000000 + seq })
	applyEvent(conversation, { ...logged(2), type: "user_message", content: [{ type: "text", text: "hi", provider_state: {} }] })
	const call = { type: "tool_call", id: "a", name: "read", arguments: { path: "gone.py", details: "the model's own" } }
	applyEvent(conversation, {
		...logged(3),
		type: "assistant_message",
		content: [{ ...call, display: [{ text: "Read gone.py" }], provider_state: { item: "x" } }],
		api: "litellm",
		model: "m",
		stop_reason: "tool_use",
	})
	applyEvent(conversation, { ...logged(4), type: "usage", input_tokens: 10, output_tokens: 2, context_window: 1000, standalone: false })
	applyEvent(conversation, { ...logged(5), type: "tool_result", tool_call_id: "a", name: "read", content: "ENOENT", is_error: true, details: { lines: 0 } })

	const [, user, assistant, tool] = buildTranscriptRows(conversation)
	assert.deepEqual(user.entry, { type: "user_message", content: [{ type: "text", text: "hi" }] })
	assert.deepEqual(assistant.entry, { type: "assistant_message", content: [call], model: "m", stop_reason: "tool_use" })
	assert.deepEqual(assistant.usage, { type: "usage", input_tokens: 10, output_tokens: 2 })
	assert.deepEqual(tool.input, call)
	assert.deepEqual(tool.output, { type: "tool_result", tool_call_id: "a", name: "read", content: "ENOENT", is_error: true })
})

test("a reply cut off before its first block still shows", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "go" })
	applyEvent(conversation, { type: "assistant_message", seq: 3, content: [], stop_reason: "aborted" })

	const assistant = buildTranscriptRows(conversation).find((row) => row.kind === "assistant")
	assert.deepEqual(assistant.entry, { type: "assistant_message", content: [], stop_reason: "aborted" })
})

test("a compaction owns the summarizer's call without moving the context reading", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	applyEvent(conversation, { type: "assistant_message", seq: 3, content: [{ type: "text", text: "hi" }] })
	applyEvent(conversation, usageEvent(4, 1000, 10))
	applyEvent(conversation, { type: "compaction", seq: 5, reason: "threshold", summary: "so far…", compact_up_to_seq: 3 })
	applyEvent(conversation, { ...usageEvent(6, 880, 120), standalone: true })

	// the summarizer prompted with the transcript, not with the new context
	assert.equal(conversation.contextTokens, 0)
	const compaction = buildTranscriptRows(conversation).find((row) => row.kind === "compaction")
	assert.equal(compaction.usage.input_tokens, 880)
	assert.equal(conversation.usage.output, 130) // its spend still counts
})

test("failed compaction usage does not attach to an assistant response", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	applyEvent(conversation, { type: "assistant_message", seq: 3, content: [{ type: "text", text: "hi" }] })
	applyEvent(conversation, { ...usageEvent(4, 880, 120), standalone: true })
	applyEvent(conversation, { type: "run_error", seq: 5, message: "summary failed" })

	assert.equal(buildTranscriptRows(conversation).find((row) => row.kind === "assistant").usage, undefined)
	assert.equal(conversation.usage.output, 120)
})

test("a sub-agent call shows what its own run spent", () => {
	const conversation = initialConversation()
	const delegate = (seq, id, args) =>
		applyEvent(conversation, {
			type: "assistant_message",
			seq,
			content: [{ type: "tool_call", id, name: "subagent", arguments: args }],
		})
	delegate(2, "s1", { description: "review the diff" })
	applyEvent(conversation, { ...usageEvent(3, 4000, 200), subagent_id: "s1", cost: 0.01 })
	applyEvent(conversation, { type: "tool_result", seq: 4, tool_call_id: "s1", name: "subagent", content: "done" })
	delegate(5, "s2", { subagent_id: "s1", description: "now the tests" }) // continues the same child
	applyEvent(conversation, { ...usageEvent(6, 5000, 300), subagent_id: "s1" })

	const rows = buildTranscriptRows(conversation)
	const [first, second] = rows.filter((row) => row.kind === "tool")
	assert.deepEqual(first.usage, { input_tokens: 4000, output_tokens: 200, cache_read_tokens: 0, cache_write_tokens: 0, cost: 0.01 })
	assert.equal(second.usage.input_tokens, 5000) // still running: what it has spent so far
	assert.ok(rows.every((row) => row.kind === "tool" || !row.usage)) // never the session's own rows
})
