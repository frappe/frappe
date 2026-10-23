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
	formatDuration,
	initialConversation,
	invokedSkills,
	modelTitle,
	normalizeSkillCommand,
	quoteBlock,
	skillSegments,
	splitCodeRefs,
	splitQuotes,
	stepLabel,
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

test("a user message splits back into its text, attachments, code refs and quotes", () => {
	const entry = {
		content: [
			{ type: "text", text: "review this" },
			{ type: "attachment", id: "a", name: "screen.png", kind: "image" },
		],
	}
	assert.equal(userText(entry), "review this")
	assert.deepEqual(userAttachments(entry).map((item) => item.name), ["screen.png"])
	assert.equal(userText({ content: "legacy" }), "legacy")

	// code references the composer appended
	const { body, refs } = splitCodeRefs("hi\n\n@src/flow_harness/agent/agent.py:10-15\n@/abs/config.py:17")
	assert.equal(body, "hi")
	assert.deepEqual(refs, [
		{ path: "src/flow_harness/agent/agent.py", start: 10, end: 15 },
		{ path: "/abs/config.py", start: 17, end: 17 },
	])
	assert.equal(codeRefLabel(refs[0]), "agent.py (10-15)")
	assert.equal(codeRefLabel(refs[1]), "config.py (17)")
	assert.deepEqual(splitCodeRefs("plain text"), { body: "plain text", refs: [] })

	// quotes added to chat travel as blockquotes under the text
	assert.equal(quoteBlock("a\n\nb"), "> a\n>\n> b")
	assert.deepEqual(splitQuotes("hi\n\n> a\n>\n> b\n\n> c"), { body: "hi", quotes: ["a\n\nb", "c"] })
	assert.deepEqual(splitQuotes("> only"), { body: "", quotes: ["only"] })
	assert.deepEqual(splitQuotes("> top\n\nplain"), { body: "> top\n\nplain", quotes: [] })
})

test("a skill message renders as the command the user typed, where they typed it", () => {
	const expanded =
		'<skill name="security-review" location="/skills/security-review/SKILL.md">\n' +
		"References are relative to /skills/security-review.\n\n" +
		"large model-only instructions\n</skill>\n\ncheck this branch"
	const entry = { type: "user_message", content: expanded }
	assert.equal(userText(entry), "/skill:security-review check this branch")
	assert.equal(conversationTitle({ entries: [entry] }), "check this branch")
	const typed = { type: "user_message", content: [{ type: "text", text: "/skill:review fix the tests" }] }
	assert.equal(conversationTitle({ entries: [], sending: [{ entry: typed }] }), "fix the tests")

	// commands later in a message render where they were typed
	const block = (name) => `<skill name="${name}" location="/skills/${name}/SKILL.md">\nbody\n</skill>`
	const later = "check /skill:review then /skill:tests"
	const laterEntry = { type: "user_message", content: `${block("review")}\n\n${block("tests")}\n\n${later}` }
	assert.deepEqual(invokedSkills(laterEntry), ["review", "tests"])
	assert.equal(userText(laterEntry), later)
	assert.equal(conversationTitle({ entries: [laterEntry] }), later)
	// a leading command gave way to its skill; a later one is still in the text
	const leading = { type: "user_message", content: `${block("review")}\n\n${block("tests")}\n\nfix with /skill:tests` }
	assert.equal(userText(leading), "/skill:review fix with /skill:tests")
	assert.equal(normalizeSkillCommand("/skill:review\nfix with /skill:tests"), "/skill:review fix with /skill:tests")
	// named again later, the server keeps the text as typed, leading command included
	const repeated = { type: "user_message", content: `${block("review")}\n\n/skill:review do /skill:review` }
	assert.equal(userText(repeated), "/skill:review do /skill:review")
	assert.equal(normalizeSkillCommand(" /skill:review do /skill:review "), "/skill:review do /skill:review")
	assert.equal(invokedSkills({ content: "plain" }), null)
	assert.deepEqual(skillSegments("a /skill:review b/skill:review /skill:other", ["review"]), [
		{ text: "a ", skill: false },
		{ text: "/skill:review", skill: true },
		{ text: " b/skill:review /skill:other", skill: false },
	])
	// a quoted line starts nothing, so it shows plain and doesn't count as typed
	assert.deepEqual(skillSegments("/skill:review\n> /skill:review", ["review"]), [
		{ text: "/skill:review", skill: true },
		{ text: "\n> /skill:review", skill: false },
	])
	const quoted = { type: "user_message", content: `${block("review")}\n\nfix\n\n> see /skill:review` }
	assert.equal(userText(quoted), "/skill:review fix\n\n> see /skill:review")
})

test("unknown tool names are humanized for future custom tools, and model ids with no name of their own too", () => {
	assert.equal(stepLabel("send_email_now"), "Send email now")
	assert.equal(stepLabel("create-calendar-event"), "Create calendar event")
	assert.equal(stepLabel("fetchAccountDetails"), "Fetch account details")
	for (const [id, title] of [
		["codex/gpt-6.1-sol", "GPT-6.1 Sol"],
		["openai/gpt-4o-mini", "GPT-4o Mini"],
		["openai/o3-mini", "o3 Mini"],
		["openrouter/deepseek/deepseek-v4.1-flash", "DeepSeek V4.1 Flash"],
		["anthropic/claude-3-5-sonnet-20241022", "Claude 3.5 Sonnet 20241022"],
		["groq/llama-3.3-70b-versatile", "Llama 3.3 70B Versatile"],
		["openrouter/anthropic/claude-fable-5:batch", "Claude Fable 5 (batch)"],
	])
		assert.equal(modelTitle(id), title)
	assert.equal(modelTitle("a/b", [{ name: "a/b", display_name: "A: B" }]), "A: B")
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

test("the status line tracks the run: Working, Retrying, Compacting, then clear", () => {
	const conversation = initialConversation()
	// the server's copy of a message keeps the turn visibly working until it ends
	applyEvent(conversation, { type: "user_message", seq: 2, content: "Review this" })
	assert.equal(conversation.running, false)
	assert.equal(conversation.liveLabel, "Working")
	for (const [event, label] of [
		[{ type: "run_started", seq: 3 }, "Working"],
		// tool names never reach the status line: the row is the tool's only UI
		[{ type: "tool_call_started", name: "read" }, "Working"],
		[{ type: "tool_call_display_ready", id: "call-1", name: "read", arguments: { path: "src/events.py" } }, "Working"],
		[{ type: "retry", status: "scheduled" }, "Retrying"],
		[{ type: "retry", status: "started" }, "Working"],
		[{ type: "compaction_started", reason: "threshold" }, "Compacting context"],
		[{ type: "compaction_ended", reason: "threshold" }, "Working"],
		// a run that ends mid-compaction, its compaction_ended never seen, leaves none behind
		[{ type: "compaction_started" }, "Compacting context"],
		[{ type: "run_ended", seq: 4, reason: "error" }, null],
	]) {
		applyEvent(conversation, event)
		assert.equal(conversation.liveLabel, label, JSON.stringify(event))
	}
	assert.equal(conversation.running, false)
	assert.equal(conversation.compacting, false)
})

test("the context reading clears on a compaction or a model change, while spend adds up", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "usage", input_tokens: 70_000, output_tokens: 1_000 })
	applyEvent(conversation, { type: "usage", input_tokens: 80_000, output_tokens: 2_000 })
	assert.equal(conversation.usage.input + conversation.usage.output, 153_000)
	assert.equal(conversation.contextTokens, 82_000)
	applyEvent(conversation, { type: "compaction", seq: 1, compact_up_to_seq: 0 })
	assert.equal(conversation.usage.input + conversation.usage.output, 153_000)
	assert.equal(conversation.contextTokens, 0)

	// the context window never carries across a model change
	applyEvent(conversation, { type: "model_changed", model: "codex/gpt-5.6-sol" })
	applyEvent(conversation, { type: "usage", input_tokens: 80_000, context_window: 272_000 })
	applyEvent(conversation, { type: "model_changed", model: "deepseek/deepseek-chat" })
	assert.equal(conversation.contextWindow, null)
	assert.equal(conversation.contextTokens, 0)
	applyEvent(conversation, { type: "usage", context_window: 1_000_000 })
	assert.equal(conversation.contextWindow, 1_000_000)
	// changing only reasoning effort keeps the selected model's known limit
	applyEvent(conversation, { type: "model_changed", model: "deepseek/deepseek-chat", reasoning_effort: "high" })
	assert.equal(conversation.contextWindow, 1_000_000)
})

test("a streamed tool call shows once its arguments are ready, in provider order; a retry drops it", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read" })
	// a repeated start renames its placeholder instead of adding a ghost step
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "edit" })
	applyEvent(conversation, { type: "tool_call_started", id: "call-2", name: "bash" })
	assert.deepEqual(conversation.partial, [
		{ type: "tool_call", id: "call-1", name: "edit", arguments: null },
		{ type: "tool_call", id: "call-2", name: "bash", arguments: null },
	])
	assert.deepEqual(toolGroups(conversation), [])
	assert.equal(conversation.liveLabel, "Working")

	const ready = (path) => ({
		type: "tool_call_display_ready",
		id: "call-1",
		name: "edit",
		arguments: { path },
		display: [{ text: "Editing file " }, { text: path, arg: "path" }],
	})
	applyEvent(conversation, { type: "tool_call_display_ready", id: "call-2", name: "bash", arguments: { command: "pwd" } })
	applyEvent(conversation, ready("ui/App.vue"))
	// metadata sent again replaces its step
	applyEvent(conversation, ready("ui/Renamed.vue"))
	assert.equal(conversation.partial.length, 2)
	const groups = toolGroups(conversation)
	assert.equal(groups.length, 1)
	assert.deepEqual(
		groups[0].steps.map((step) => [step.call.id, step.call.arguments]),
		[
			["call-1", { path: "ui/Renamed.vue" }],
			["call-2", { command: "pwd" }],
		],
	)

	// a failed attempt leaves no ghost steps
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

test("a streamed thought and call hand over to the durable message, keeping their ids", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "run_started" })
	applyEvent(conversation, { type: "user_message", seq: 1, content: "hi" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "let me see" })
	const thinking = () => buildItems(conversation).find((item) => item.kind === "thinking")
	assert.equal(thinking().key, "turn:1:th:0")
	assert.equal(thinking().block.thinking, "let me see")
	assert.equal(thinking().live, true)

	// a call's identity alone ends the thought, but neither hides it nor shows a row
	applyEvent(conversation, { type: "tool_call_started", id: "call-1", name: "read" })
	assert.equal(thinking().block.thinking, "let me see")
	assert.equal(thinking().live, false)
	assert.equal(conversation.liveLabel, "Working")
	assert.deepEqual(toolGroups(conversation), [])

	// its arguments move the thought, id and all, into the call's group
	const display = [{ text: "Reading file " }, { text: "src/app.js", arg: "path" }]
	applyEvent(conversation, {
		type: "tool_call_display_ready",
		id: "call-1",
		name: "read",
		arguments: { path: "src/app.js" },
		display,
	})
	const ids = () => toolGroups(conversation)[0].steps.map((step) => step.call?.id ?? step.id)
	assert.equal(thinking(), undefined)
	assert.deepEqual(ids(), ["turn:1:th:0", "call-1"])
	assert.deepEqual(toolGroups(conversation)[0].steps[1].call.display, display)

	// the durable message replaces the preview; a text-less (redacted) thought that never
	// streamed takes no ordinal, and whitespace-only text renders nothing
	const call = { type: "tool_call", id: "call-1", name: "read", arguments: { path: "src/app.js" }, display }
	applyEvent(conversation, {
		type: "assistant_message",
		seq: 2,
		content: [
			{ type: "thinking", thinking: "", redacted: true },
			{ type: "thinking", thinking: "let me see" },
			{ type: "text", text: "  " },
			call,
		],
		stop_reason: "tool_use",
	})
	assert.deepEqual(conversation.partial, [])
	applyEvent(conversation, { type: "tool_result", seq: 3, tool_call_id: "call-1", name: "read", content: "contents" })
	assert.deepEqual(buildItems(conversation).map((item) => item.kind), ["user", "group"])
	assert.deepEqual(ids(), ["th:2:0", "turn:1:th:0", "call-1"])
	const [group] = toolGroups(conversation)
	assert.equal(group.key, "g:call-1")
	assert.deepEqual(group.steps[1].thought, { type: "thinking", thinking: "let me see" })
	assert.strictEqual(group.steps[2].call, call)
	assert.equal(group.steps[2].result.content, "contents")

	// the next thought streams into the group's dropdown, and settles once the next call starts
	applyEvent(conversation, { type: "thinking_delta", thinking: "now write" })
	assert.equal(conversation.liveLabel, "Thinking")
	assert.equal(thinking(), undefined)
	assert.deepEqual(ids(), ["th:2:0", "turn:1:th:0", "call-1", "turn:1:th:1"])
	const last = () => toolGroups(conversation)[0].steps[3]
	assert.deepEqual(last().thought, { type: "thinking", thinking: "now write" })
	assert.equal(last().live, true)
	applyEvent(conversation, { type: "tool_call_started", id: "call-2", name: "write" })
	assert.equal(last().live, false)
	assert.equal(conversation.liveLabel, "Working")
})

test("streamed thought, text, and tool call keep their order and keys until the durable message", () => {
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
	assert.equal(durableItems[3].key, "g:call-1")

	// a later text keeps its own key from the streamed preview to the durable message
	applyEvent(conversation, { type: "tool_result", seq: 3, tool_call_id: "call-1", content: "a.js" })
	applyEvent(conversation, { type: "text_delta", text: "| a |" })
	const textKeys = () => buildItems(conversation).filter((item) => item.kind === "text").map((item) => item.key)
	const live = textKeys()
	applyEvent(conversation, { type: "assistant_message", seq: 4, content: [{ type: "text", text: "| a |" }] })
	assert.deepEqual(textKeys(), live)
	assert.equal(new Set(live).size, 2)
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

test("a settled turn stays folded while the next runs, with messages on their way below", () => {
	const conversation = initialConversation()
	// no timestamps: a plain Worked label
	for (const entry of [
		{ type: "user_message", seq: 1, content: "First" },
		{
			type: "assistant_message",
			seq: 2,
			content: [
				{ type: "thinking", thinking: "First thought" },
				{ type: "text", text: "First answer" },
			],
			stop_reason: "stop",
		},
		{ type: "run_ended", seq: 3, reason: "done" },
	]) applyEvent(conversation, entry)
	const settled = buildItems(conversation).map((item) => item.kind)
	assert.deepEqual(settled, ["user", "turn-fold", "text", "turn-copy"])
	assert.equal(buildItems(conversation)[1].label, "Worked")

	conversation.sending.push({
		key: "sending:1",
		entry: { type: "user_message", content: "Second", ts: 20 },
	})
	// the run starts before the server's copy of the message that started it
	applyEvent(conversation, { type: "run_started", seq: 4, ts: 20 })
	assert.deepEqual(buildItems(conversation).map((item) => item.kind), [...settled, "user"])
	// a message steered into that run waits below the one still on its way
	conversation.steering.push({ key: "steering:2", entry: { type: "user_message", content: "And this", ts: 21 } })
	assert.deepEqual(
		buildItems(conversation).slice(-2).map((item) => item.key),
		["sending:1", "steering:2"],
	)

	// the running turn never folds, and the steered message waits below it without settling it
	applyEvent(conversation, { type: "user_message", seq: 5, ts: 20, content: "Second" })
	applyEvent(conversation, { type: "thinking_delta", thinking: "Still working" })
	const items = buildItems(conversation)
	assert.deepEqual(items.map((item) => item.kind), [...settled, "user", "thinking", "user"])
	assert.equal(items.at(-2).live, true)
	assert.equal(items.at(-1).key, "steering:2")
	assert.deepEqual(items.slice(0, -1), buildItems({ ...conversation, steering: [] }))
})

test("a turn folds only once its run ends, approval pauses and steered messages included, and a running reply counts from its run's start", () => {
	const conversation = initialConversation()
	for (const event of [
		{ type: "run_started", seq: 1, ts: 100 },
		{ type: "user_message", seq: 2, ts: 100, content: "Change it" },
		{
			type: "assistant_message",
			seq: 3,
			ts: 105,
			content: [
				{ type: "thinking", thinking: "This needs approval." },
				{ type: "text", text: "Let me write a.js." },
				{ type: "tool_call", id: "call-1", name: "write", arguments: { path: "a.js" } },
			],
			stop_reason: "tool_use",
		},
		{ type: "approval_required", seq: 4, ts: 105, calls: [{ id: "call-1", name: "write", args: { path: "a.js" } }] },
		{ type: "run_ended", seq: 5, ts: 105, reason: "paused" },
	])
		applyEvent(conversation, event)
	// paused, nothing folds; the gated call waits in the approval card
	assert.deepEqual(buildItems(conversation).map((item) => item.kind), ["user", "thinking", "text"])

	// a message steered into the resumed run joins its turn
	for (const event of [
		{ type: "run_started", seq: 6, ts: 110 },
		{ type: "tool_result", seq: 7, ts: 110, tool_call_id: "call-1", content: "[wrote]" },
		{ type: "user_message", seq: 8, ts: 112, content: "Also b.js" },
		{
			type: "assistant_message",
			seq: 9,
			ts: 115,
			content: [{ type: "tool_call", id: "call-2", name: "write", arguments: { path: "b.js" } }],
			stop_reason: "tool_use",
		},
		{ type: "tool_result", seq: 10, ts: 116, tool_call_id: "call-2", content: "[wrote]" },
	])
		applyEvent(conversation, event)
	assert.deepEqual(buildItems(conversation).map((item) => item.kind), ["user", "thinking", "text", "group", "user", "group"])

	applyEvent(conversation, {
		type: "assistant_message",
		seq: 11,
		ts: 130,
		content: [{ type: "text", text: "Done." }],
		stop_reason: "stop",
	})
	applyEvent(conversation, { type: "run_ended", seq: 12, ts: 130.5, reason: "done" })

	const collapsed = buildItems(conversation)
	assert.deepEqual(collapsed.map((item) => item.kind), ["user", "turn-fold", "user", "text", "turn-copy"])
	assert.equal(collapsed[1].label, "Worked for 30s")
	assert.equal(collapsed.at(-1).text, "Done.")
	const expanded = buildItems(conversation, new Set([collapsed[1].turnKey]))
	assert.deepEqual(expanded.map((item) => item.kind), [
		"user",
		"turn-fold",
		"thinking",
		"text",
		"group",
		"user",
		"group",
		"text",
		"turn-copy",
	])
})

test("a /compact after a turn leaves it folded, adds no time to it, and sits below its copy row", () => {
	const conversation = initialConversation()
	for (const event of [
		{ type: "run_started", seq: 1, ts: 10 },
		{ type: "user_message", seq: 2, ts: 10, content: "Fix it" },
		{
			type: "assistant_message",
			seq: 3,
			ts: 12,
			content: [{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "ls" } }],
			stop_reason: "tool_use",
		},
		{ type: "tool_result", seq: 4, ts: 13, tool_call_id: "call-1", content: "ok" },
		{ type: "assistant_message", seq: 5, ts: 15, content: [{ type: "text", text: "Done." }], stop_reason: "stop" },
		{ type: "run_ended", seq: 6, ts: 15, reason: "done" },
		{ type: "run_started", seq: 7, ts: 3600 },
		{ type: "compaction_started", reason: "manual" },
	])
		applyEvent(conversation, event)
	assert.deepEqual(buildItems(conversation).map((item) => item.kind), ["user", "turn-fold", "text", "turn-copy"])

	applyEvent(conversation, { type: "compaction_ended", reason: "manual" })
	assert.equal(conversation.liveLabel, null)
	applyEvent(conversation, { type: "compaction", seq: 8, ts: 3700, reason: "manual", summary: "Fixed it.", compact_up_to_seq: 6 })
	applyEvent(conversation, { type: "run_ended", seq: 9, ts: 3700, reason: "done" })
	const collapsed = buildItems(conversation)
	assert.equal(collapsed[1].label, "Worked for 5s")
	const expanded = buildItems(conversation, new Set([collapsed[1].turnKey]))
	assert.deepEqual(expanded.map((item) => item.kind), [
		"user",
		"turn-fold",
		"group",
		"text",
		"turn-copy",
		"compaction",
	])
})

test("a turn's last text and all after it stay out of its fold, the copy row closing them", () => {
	const closing = (content) => [
		{ type: "assistant_message", seq: 5, ts: 14, content, stop_reason: "stop" },
		{ type: "run_ended", seq: 6, ts: 14, reason: "done" },
	]
	for (const [ending, kinds] of [
		// an empty closing message leaves the answer and the call after it standing
		[closing([]), ["user", "text", "group", "turn-copy"]],
		[closing([{ type: "text", text: "\n" }]), ["user", "text", "group", "turn-copy"]],
		[closing([{ type: "thinking", thinking: "Done." }]), ["user", "text", "group", "turn-copy"]],
		// as does one that only suggests the user's replies, which show under the thread, never as a row
		[
			closing([{ type: "tool_call", id: "s1", name: "suggest_replies", arguments: { replies: ["Send it", "Not yet"] } }]),
			["user", "text", "group", "turn-copy"],
		],
		// and calls in a message of their own after it
		[
			[
				{ type: "assistant_message", seq: 5, ts: 14, content: [{ type: "tool_call", id: "call-2", name: "update_memory", arguments: {} }] },
				{ type: "tool_result", seq: 6, ts: 14, tool_call_id: "call-2", content: "saved" },
				...closing([]).map((event) => ({ ...event, seq: event.seq + 2 })),
			],
			["user", "text", "group", "turn-copy"],
		],
		// a run cut off at its turn limit: the copy row goes below the work and the notice
		[[{ type: "run_ended", seq: 5, ts: 14, reason: "max_turns" }], ["user", "text", "group", "notice", "turn-copy"]],
	]) {
		const conversation = initialConversation()
		for (const event of [
			{ type: "run_started", seq: 1, ts: 10 },
			{ type: "user_message", seq: 2, ts: 10, content: "Make the invoice" },
			{
				type: "assistant_message",
				seq: 3,
				ts: 12,
				content: [
					{ type: "text", text: "Created invoice INV-1." },
					{ type: "tool_call", id: "call-1", name: "update_memory", arguments: { note: "INV-1" } },
				],
				stop_reason: "tool_use",
			},
			{ type: "tool_result", seq: 4, ts: 13, tool_call_id: "call-1", content: "saved" },
			...ending,
		])
			applyEvent(conversation, event)

		const items = buildItems(conversation)
		assert.deepEqual(items.map((item) => item.kind), kinds, JSON.stringify(ending))
		assert.equal(items.at(-1).text, "Created invoice INV-1.")
	}
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

test("a turn the user stopped or denied folds all its text with the work", () => {
	for (const [events, label, expanded] of [
		[
			[
				{ type: "run_started", seq: 1, ts: 30 },
				{ type: "user_message", seq: 2, ts: 30, content: "Do it" },
				{
					type: "assistant_message",
					seq: 3,
					ts: 32,
					content: [
						{ type: "text", text: "I will run a command." },
						{ type: "tool_call", id: "call-1", name: "bash", arguments: { command: "echo hi" } },
					],
					stop_reason: "tool_use",
				},
				{ type: "tool_result", seq: 4, ts: 33, tool_call_id: "call-1", content: "hi" },
				{ type: "assistant_message", seq: 5, ts: 36, content: [{ type: "text", text: "Partial resp" }], stop_reason: "aborted" },
				{ type: "run_ended", seq: 6, ts: 36, reason: "aborted" },
			],
			"You stopped after 6s",
			// the commentary, the tool group, and the aborted partial
			["user", "turn-fold", "text", "group", "text", "notice"],
		],
		[
			[
				{ type: "run_started", seq: 1, ts: 10 },
				{ type: "user_message", seq: 2, ts: 10, content: "Create it" },
				{
					type: "assistant_message",
					seq: 3,
					ts: 14,
					content: [
						{ type: "text", text: "Let me create it now." },
						{ type: "tool_call", id: "call-1", name: "write", arguments: { path: "hello.html" } },
					],
					stop_reason: "tool_use",
				},
				{ type: "approval_required", seq: 4, ts: 14, calls: [{ id: "call-1", name: "write", args: { path: "hello.html" } }] },
				{ type: "run_ended", seq: 5, ts: 14, reason: "paused" },
				{ type: "run_started", seq: 6, ts: 17 },
				{
					type: "tool_result",
					seq: 7,
					ts: 17,
					tool_call_id: "call-1",
					content: '{"status": "denied", "message": "User denied this tool call."}',
					is_error: true,
				},
				{ type: "run_ended", seq: 8, ts: 17, reason: "denied" },
			],
			"Worked for 7s",
			["user", "turn-fold", "text", "group", "notice"],
		],
	]) {
		const conversation = initialConversation()
		for (const event of events) applyEvent(conversation, event)
		const collapsed = buildItems(conversation)
		assert.deepEqual(collapsed.map((item) => item.kind), ["user", "turn-fold", "notice"], label)
		assert.equal(collapsed[1].label, label)
		assert.deepEqual(buildItems(conversation, new Set([collapsed[1].turnKey])).map((item) => item.kind), expanded, label)
	}
})

test("a settled turn lists the files its successful edits and writes changed", () => {
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
	// none while the turn runs
	assert.ok(!buildItems(conversation).some((item) => item.kind === "turn-files"))
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

test("usage goes to the response that made the call, never a message or tool result", () => {
	const conversation = initialConversation()
	assert.deepEqual(buildTranscriptRows(conversation), [])
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	repliedWith(conversation, 3, ["a", "b"])
	applyEvent(conversation, usageEvent(4, 1000, 10))
	applyEvent(conversation, { type: "tool_result", seq: 5, tool_call_id: "a", name: "read", content: "x".repeat(400) })
	applyEvent(conversation, { type: "tool_result", seq: 6, tool_call_id: "b", name: "read", content: "x".repeat(1200) })
	repliedWith(conversation, 7, [])
	applyEvent(conversation, usageEvent(8, 1410, 20))
	// an aborted response's empty usage report is not a model call
	applyEvent(conversation, { type: "assistant_message", seq: 9, content: [{ type: "text", text: "x".repeat(400) }], stop_reason: "aborted" })
	applyEvent(conversation, { type: "usage", seq: 10 }) // what the adapters yield on cancel
	applyEvent(conversation, { type: "run_ended", seq: 11, reason: "aborted" })
	applyEvent(conversation, { type: "user_message", seq: 12, content: "again" })
	repliedWith(conversation, 13, [])
	applyEvent(conversation, usageEvent(14, 1200, 20))

	assert.deepEqual(conversation.requests.map((usage) => usage.seq), [4, 8, 14])
	const rows = buildTranscriptRows(conversation)
	// the system prompt opens the transcript as a stand-in, never its text
	assert.equal(rows[0].body, "System prompt.")
	assert.deepEqual(
		rows.map((row) => [row.kind, row.usage?.input_tokens]),
		[
			["system", undefined],
			["user", undefined],
			["assistant", 1000],
			["tool", undefined],
			["tool", undefined],
			["assistant", 1410],
			["assistant", undefined],
			["user", undefined],
			["assistant", 1200],
		],
	)
	assert.equal(rows[2].usage.output_tokens, 10)
	assert.equal(rows[6].usage, undefined)
	assert.ok(rows.every((row) => row.kind === "assistant" || row.usage === undefined))
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
	// a reply cut off before its first block still shows
	applyEvent(conversation, { ...logged(6), type: "assistant_message", content: [], stop_reason: "aborted" })

	const [, user, assistant, tool, cut] = buildTranscriptRows(conversation)
	assert.deepEqual(user.entry, { type: "user_message", content: [{ type: "text", text: "hi" }] })
	assert.deepEqual(assistant.entry, { type: "assistant_message", content: [call], model: "m", stop_reason: "tool_use" })
	assert.deepEqual(assistant.usage, { type: "usage", input_tokens: 10, output_tokens: 2 })
	assert.deepEqual(tool.input, call)
	assert.deepEqual(tool.output, { type: "tool_result", tool_call_id: "a", name: "read", content: "ENOENT", is_error: true })
	assert.deepEqual(cut.entry, { type: "assistant_message", content: [], stop_reason: "aborted" })
})

test("a summarizer's call belongs to its compaction, never a response or the context reading", () => {
	const conversation = initialConversation()
	applyEvent(conversation, { type: "user_message", seq: 2, content: "hello" })
	applyEvent(conversation, { type: "assistant_message", seq: 3, content: [{ type: "text", text: "hi" }] })
	applyEvent(conversation, usageEvent(4, 1000, 10))
	applyEvent(conversation, { type: "compaction", seq: 5, reason: "threshold", summary: "so far…", compact_up_to_seq: 3 })
	applyEvent(conversation, { ...usageEvent(6, 880, 120), standalone: true })
	// the summarizer prompted with the transcript, not with the new context
	assert.equal(conversation.contextTokens, 0)
	// a summary that failed right after a response leaves its call to no row
	applyEvent(conversation, { type: "assistant_message", seq: 7, content: [{ type: "text", text: "more" }] })
	applyEvent(conversation, { ...usageEvent(8, 500, 50), standalone: true })
	applyEvent(conversation, { type: "run_error", seq: 9, message: "summary failed" })

	const rows = buildTranscriptRows(conversation)
	assert.equal(rows.find((row) => row.kind === "compaction").usage.input_tokens, 880)
	assert.equal(rows.find((row) => row.key === "a:7").usage, undefined)
	assert.equal(conversation.usage.output, 180) // its spend still counts
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
