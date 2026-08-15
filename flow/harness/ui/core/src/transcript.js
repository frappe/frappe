// Pure event → view-model logic. Mirrors the server's reducer semantics
// (flow_tui/client/state.py is the reference): replay and live share one code
// path, durable entries rebuild everything, deltas are presentation-only.

export const EFFORTS = ["default", "off", "minimal", "low", "medium", "high", "xhigh", "max"]

// display names for the wire-level effort ids
export const EFFORT_LABELS = {
	default: "Default",
	off: "Off",
	minimal: "Minimal",
	low: "Low",
	medium: "Medium",
	high: "High",
	xhigh: "X-High",
	max: "Max",
}

export function initialConversation() {
	return {
		entries: [],
		// Ordered, presentation-only assistant blocks accumulated from streaming
		// deltas. The terminal assistant_message atomically replaces this preview.
		partial: [],
		running: false,
		compacting: false,
		pendingApproval: null, // { seq, calls: [PendingCall], answers: {id: string} }
		model: null,
		reasoningEffort: null,
		usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0 },
		contextTokens: 0,
		contextWindow: null,
		latestSeq: 0,
		lastError: null,
		liveLabel: null,
		needsReload: false,
		// errors witnessed live this page-load show in full; replayed ones are
		// just a marker (the store records which seqs arrived live)
		liveErrorSeqs: [],
	}
}

function appendPartialText(partial, text) {
	if (!text) return
	const tail = partial[partial.length - 1]
	if (tail?.type === "text") tail.text += text
	else partial.push({ type: "text", text })
}

function appendPartialThinking(partial, thinking) {
	if (!thinking) return
	const tail = partial[partial.length - 1]
	if (tail?.type === "thinking") tail.thinking += thinking
	else partial.push({ type: "thinking", thinking })
}

// Applies one wire event. Returns the state for chaining.
export function applyEvent(s, e) {
	if (typeof e.seq === "number") s.latestSeq = Math.max(s.latestSeq, e.seq)
	switch (e.type) {
		case "run_started":
			s.running = true
			s.lastError = null
			s.liveLabel = "Thinking"
			s.partial = []
			s.pendingApproval = null // a new run consumes the batch (resume) — same as the server reducer
			break
		case "user_message":
		case "assistant_message":
		case "tool_result":
			if (e.type === "assistant_message") {
				s.partial = []
				// a text blob ends the tool phase; a tool-only message keeps the
				// current tool label until the next one replaces it
				if ((e.content ?? []).some((b) => b.type === "text" && b.text)) s.liveLabel = null
			}
			if (e.type === "tool_result" && s.pendingApproval) {
				// cancel_pending answers gated calls without a run; drop them from the batch
				const calls = s.pendingApproval.calls.filter((c) => c.id !== e.tool_call_id)
				s.pendingApproval = calls.length ? { ...s.pendingApproval, calls } : null
			}
			s.entries.push(e)
			break
		case "compaction":
			s.entries.push(e)
			// The compacted summary has a different context size. Until the next
			// provider report arrives, the old pre-compaction count is invalid.
			s.contextTokens = 0
			break
		case "approval_required":
			s.pendingApproval = { seq: e.seq, calls: e.calls, answers: {} }
			break
		case "run_ended":
			s.running = false
			s.liveLabel = null
			s.partial = []
			if (e.reason !== "paused") s.pendingApproval = null // a pause outlives its run
			// abnormal endings leave a durable marker in the transcript flow
			if (["aborted", "max_turns", "budget", "length"].includes(e.reason)) s.entries.push(e)
			break
		case "model_changed":
			if (s.model !== e.model) s.contextWindow = null
			s.model = e.model
			s.reasoningEffort = e.reasoning_effort ?? null
			s.contextTokens = 0
			break
		case "usage":
			s.usage.input += e.input_tokens ?? 0
			s.usage.output += e.output_tokens ?? 0
			s.usage.cacheRead += e.cache_read_tokens ?? 0
			s.usage.cacheWrite += e.cache_write_tokens ?? 0
			s.usage.cost += e.cost ?? 0
			if (e.context_window != null) s.contextWindow = e.context_window
			if ((e.input_tokens ?? 0) + (e.output_tokens ?? 0) > 0)
				s.contextTokens = (e.input_tokens ?? 0) + (e.output_tokens ?? 0)
			break
		case "run_error":
			s.lastError = e
			// A failed tool announcement must not survive as a ghost step. Preserve
			// any text/thinking preview until the terminal run_ended event clears it.
			s.partial = s.partial.filter((block) => block.type !== "tool_call")
			s.entries.push(e) // rendered in place, and it survives a reload
			break
		case "rewind":
			// Entries before the target may be retracted; a full replay is the
			// only always-correct recovery. The store watches this flag.
			s.needsReload = true
			break
		case "text_delta":
			appendPartialText(s.partial, e.text)
			s.liveLabel = null
			break
		case "thinking_delta":
			appendPartialThinking(s.partial, e.thinking)
			s.liveLabel = "Thinking"
			break
		case "tool_call_started":
			// Preserve the provider's block order without rendering a metadata-free
			// tool row. tool_call_display_ready upgrades this placeholder in place.
			if (e.id && e.name) {
				const existing = s.partial.find((block) => block.type === "tool_call" && block.id === e.id)
				if (existing) existing.name = e.name
				else s.partial.push({ type: "tool_call", id: e.id, name: e.name, arguments: null })
			}
			// The tool name alone already names the activity; streamed arguments
			// upgrade it to the richer display once tool_call_display_ready lands.
			s.liveLabel = stepLiveLabel({ name: e.name })
			break
		case "tool_call_display_ready": {
			const call = {
				type: "tool_call",
				id: e.id,
				name: e.name,
				arguments: e.arguments ?? {},
				display: e.display ?? null,
			}
			const index = s.partial.findIndex((block) => block.type === "tool_call" && block.id === e.id)
			if (index === -1) s.partial.push(call)
			else s.partial[index] = call
			s.liveLabel = stepLiveLabel(call)
			break
		}
		case "retry":
			if (e.status === "started") {
				// the boundary where a failed attempt's deltas must be discarded.
				// liveLabel resets too: "Retrying" must not stick through the new attempt.
				s.partial = []
				s.liveLabel = null
			} else if (e.status === "scheduled") {
				s.liveLabel = "Retrying"
			}
			break
		case "compaction_started":
			s.compacting = true
			s.liveLabel = "Compacting context"
			break
		case "compaction_ended":
			s.compacting = false
			s.liveLabel = null
			break
	}
	return s
}

const END_NOTICES = {
	aborted: "Interrupted by user",
	max_turns: "Stopped — turn limit reached",
	budget: "Stopped — output budget reached",
	length: "Stopped — model hit its length limit",
}

const STEP_LABELS = {
	read_file: "Reading file",
	grep: "Searching code",
	bash: "Running command",
	edit: "Editing file",
	write: "Writing file",
}

export function stepLabel(name) {
	return STEP_LABELS[name] ?? humanizeToolName(name)
}

export function humanizeToolName(name) {
	const words = String(name ?? "")
		.replace(/([a-z0-9])([A-Z])/g, "$1 $2")
		.replace(/[_-]+/g, " ")
		.trim()
		.toLowerCase()
	return words ? words[0].toUpperCase() + words.slice(1) : "Tool"
}

function lowerFirst(value) {
	return value ? value[0].toLowerCase() + value.slice(1) : value
}

function fileName(path) {
	return String(path ?? "")
		.split(/[\\/]/)
		.filter(Boolean)
		.pop()
}

export function displayText(display) {
	return display.map((segment) => segment.text).join("")
}

export function stepLiveLabel(call) {
	const name = call?.name ?? ""
	if (call?.display?.length) {
		// the live line shows only the file name for file tools; the dropdown keeps the full path
		if (["read_file", "write", "edit"].includes(name))
			return call.display
				.map((segment) => (segment.arg === "path" ? fileName(segment.text) : segment.text))
				.join("")
		return displayText(call.display)
	}
	const label = stepLabel(name)
	if (["read_file", "write", "edit"].includes(name)) {
		const subject = fileName((call.arguments ?? call.args ?? {}).path)
		return subject ? `${label} ${subject}` : label
	}
	if (name in STEP_LABELS) return label
	return `Running ${lowerFirst(label)}`
}

// Keep the live header on meaningful work. Reasoning deltas remain available
// inside the expanded group, but a generic "Thinking" signal should not replace
// the latest actionable tool metadata.
export function toolGroupLiveLabel(steps, liveLabel) {
	const toolSteps = steps.filter((step) => step.call)
	const running = toolSteps.find((step) => !step.result && !step.aborted)
	if (running) return stepLiveLabel(running.call)
	const last = toolSteps.at(-1)
	const lastLabel = last ? stepLiveLabel(last.call) : null
	if (
		last &&
		(!liveLabel ||
			liveLabel === "Thinking" ||
			liveLabel === stepLabel(last.call.name) ||
			liveLabel === lastLabel)
	)
		return lastLabel
	return liveLabel ?? lastLabel
}

export function toolGroupSummary(calls) {
	const activities = []
	const counts = new Map()
	for (const call of calls) {
		const name = call?.name ?? ""
		const key =
			name === "write" || name === "edit"
				? "files-edited"
				: name === "read_file"
					? "files-read"
					: name === "bash"
						? "commands"
						: name === "grep"
							? "search"
							: `custom:${name}`
		if (!counts.has(key)) activities.push({ key, name })
		counts.set(key, (counts.get(key) ?? 0) + 1)
	}
	const phrases = activities.map(({ key, name }) => {
		const count = counts.get(key)
		if (key === "files-edited") return count === 1 ? "edited file" : "edited files"
		if (key === "files-read") return count === 1 ? "read file" : "read files"
		if (key === "commands") return count === 1 ? "ran command" : "ran commands"
		if (key === "search") return "searched code"
		return `used ${lowerFirst(humanizeToolName(name))}`
	})
	const summary = phrases.join(", ")
	return summary ? summary[0].toUpperCase() + summary.slice(1) : "Worked"
}

// The one-line summary shown next to a step label.
export function stepSubject(call) {
	const a = call.arguments ?? call.args ?? {}
	switch (call.name) {
		case "read_file":
		case "write":
			return a.path ?? ""
		case "edit":
			return a.path ?? ""
		case "grep":
			return a.pattern ?? ""
		case "bash":
			return a.command ?? ""
		default: {
			const first = Object.values(a)[0]
			return typeof first === "string" ? first : ""
		}
	}
}

// A tool_result whose content is the loop's decision envelope (deny/cancel/redirect).
export function stepDecision(result) {
	const content = result?.content
	if (!content || !content.startsWith("{")) return null
	try {
		const parsed = JSON.parse(content)
		return ["denied", "cancelled", "redirect"].includes(parsed.status) ? parsed : null
	} catch {
		return null
	}
}

// Right-aligned stat for a finished step, from tool_result details.
export function stepStat(step) {
	const decision = stepDecision(step.result)
	if (decision) {
		return { denied: "denied", cancelled: "cancelled", redirect: "change requested" }[decision.status]
	}
	const d = step.result?.details
	if (!d) return ""
	if (d.exit_code !== undefined && d.exit_code !== null) return `exit ${d.exit_code}`
	if (d.matches !== undefined) return `${d.matches} matches`
	if (d.lines_added !== undefined || d.lines_removed !== undefined)
		return `+${d.lines_added ?? 0} -${d.lines_removed ?? 0}`
	if (d.edits !== undefined) return `${d.edits} edits`
	if (d.lines !== undefined) return `${d.lines} lines`
	if (d.total_lines !== undefined) return `${d.total_lines} lines`
	if (d.chars !== undefined) return `${d.chars} chars`
	return ""
}

// Matches t3code's compact elapsed-time buckets without relying on wall-clock
// timers for settled history.
export function formatDuration(durationMs) {
	if (!Number.isFinite(durationMs) || durationMs < 0) return "0ms"
	if (durationMs < 1_000) return `${Math.max(1, Math.round(durationMs))}ms`
	const roundedSeconds = Math.round(durationMs / 1_000)
	if (roundedSeconds < 60) return `${roundedSeconds}s`
	const minutes = Math.floor(roundedSeconds / 60)
	const seconds = roundedSeconds % 60
	if (seconds === 0) return `${minutes}m`
	return `${minutes}m ${seconds}s`
}

function deriveTurns(entries) {
	const turns = new Map()
	const turnByEntry = new Map()
	let current = null

	for (const [index, entry] of entries.entries()) {
		if (entry.type === "user_message") {
			current = {
				key: `turn:${entry.seq ?? index}`,
				hasUser: true,
				startedAt: Number.isFinite(entry.ts) ? entry.ts : null,
				endedAt: Number.isFinite(entry.ts) ? entry.ts : null,
				terminalAssistant: null,
				interrupted: false,
			}
			turns.set(current.key, current)
		} else if (!current && entry.type === "assistant_message") {
			// Preserve copy/timestamp behavior for legacy or synthetic transcripts
			// that contain assistant output without a user boundary. These are never
			// folded because their start time is ambiguous.
			current = {
				key: `turn:implicit:${entry.seq ?? index}`,
				hasUser: false,
				startedAt: Number.isFinite(entry.ts) ? entry.ts : null,
				endedAt: Number.isFinite(entry.ts) ? entry.ts : null,
				terminalAssistant: null,
				interrupted: false,
			}
			turns.set(current.key, current)
		}

		if (!current) continue
		turnByEntry.set(entry, current.key)
		if (Number.isFinite(entry.ts)) {
			current.endedAt = current.endedAt == null ? entry.ts : Math.max(current.endedAt, entry.ts)
		}
		if (entry.type === "assistant_message") current.terminalAssistant = entry
		if (entry.type === "run_ended" && entry.reason === "aborted") current.interrupted = true
	}

	return { turns, turnByEntry, latestTurnKey: [...turns.keys()].at(-1) ?? null }
}

function foldLabel(turn) {
	const elapsed =
		turn.startedAt != null && turn.endedAt != null
			? formatDuration(Math.max(0, turn.endedAt - turn.startedAt) * 1_000)
			: null
	if (turn.interrupted) return elapsed ? `You stopped after ${elapsed}` : "You stopped this response"
	return elapsed ? `Worked for ${elapsed}` : "Worked"
}

// Folds durable entries and the streaming preview into renderable items:
//   {kind: "user", entry}
//   {kind: "text", block, entry?, provisional?}
//   {kind: "thinking", block, entry?, live?}
//   {kind: "group", steps: [{call, result, aborted} | {thought}]}
//   {kind: "turn-fold", turnKey, label, expanded}
//   {kind: "approval", calls: [...], seq}      (undecided batch)
//   {kind: "compaction", entry}
//   {kind: "error", error}
// Every item carries a stable `key` (derived from seq / call id) so v-for
// state (expanded panels) survives the tail reshaping while streaming.
// Consecutive tool steps merge into one group; only a text/user item seals it.
// Thinking never splits a group: a thought adjacent to tool calls becomes a
// {thought} row inside the group, and stands alone only when no tools surround
// it (a pure thinking + text turn).
export function buildItems(conversation, expandedTurnKeys = new Set()) {
	const items = []
	const stepsById = new Map()
	const pending = conversation.pendingApproval
	const pendingIds = new Set(pending?.calls.map((c) => c.id) ?? [])
	const { turns, turnByEntry, latestTurnKey } = deriveTurns(conversation.entries)
	let currentTurnKey = null
	let bufferedThoughts = []

	const currentGroup = (firstCallId) => {
		const last = items[items.length - 1]
		if (last?.kind === "group") return last
		const group = { kind: "group", key: `g:${firstCallId}`, turnKey: currentTurnKey, steps: [] }
		items.push(group)
		return group
	}
	// thoughts not claimed by a tool group render as standalone blocks
	const flushThoughts = () => {
		for (const t of bufferedThoughts) {
			items.push({
				kind: "thinking",
				key: t.key,
				turnKey: t.turnKey,
				block: t.block,
				entry: t.entry,
				live: t.live,
			})
		}
		bufferedThoughts = []
	}
	const appendAssistantBlocks = (blocks, { entry = null, provisional = false } = {}) => {
		for (const [blockIdx, block] of blocks.entries()) {
			const key = provisional
				? `p:${blockIdx}`
				: `${block.type === "thinking" ? "th" : "t"}:${entry.seq}:${blockIdx}`
			if (block.type === "text" && block.text) {
				flushThoughts()
				items.push({ kind: "text", key, turnKey: currentTurnKey, block, entry, provisional })
			} else if (block.type === "thinking") {
				const last = items[items.length - 1]
				if (last?.kind === "group") last.steps.push({ thought: block })
				else {
					bufferedThoughts.push({
						block,
						entry,
						key,
						turnKey: currentTurnKey,
						live: provisional && blockIdx === blocks.length - 1,
					})
				}
			} else if (block.type === "tool_call") {
				if (provisional && block.arguments == null) continue
				if (pendingIds.has(block.id) || stepsById.has(block.id)) continue
				const group = currentGroup(block.id)
				for (const thought of bufferedThoughts) group.steps.push({ thought: thought.block })
				bufferedThoughts = []
				const step = {
					call: block,
					result: null,
					aborted: !provisional && entry.stop_reason === "aborted",
				}
				stepsById.set(block.id, step)
				group.steps.push(step)
			}
		}
	}

	for (const entry of conversation.entries) {
		currentTurnKey = turnByEntry.get(entry) ?? currentTurnKey
		if (entry.type === "user_message") {
			flushThoughts()
			items.push({ kind: "user", key: `u:${entry.seq}`, entry })
		} else if (entry.type === "assistant_message") {
			appendAssistantBlocks(entry.content ?? [], { entry })
		} else if (entry.type === "tool_result") {
			const step = stepsById.get(entry.tool_call_id)
			if (step) step.result = entry
		} else if (entry.type === "compaction") {
			flushThoughts()
			items.push({ kind: "compaction", key: `c:${entry.seq}`, turnKey: currentTurnKey, entry })
		} else if (entry.type === "run_error") {
			flushThoughts()
			if (conversation.liveErrorSeqs.includes(entry.seq)) {
				items.push({ kind: "error", key: `e:${entry.seq}`, turnKey: currentTurnKey, error: entry })
			} else {
				items.push({ kind: "notice", key: `n:${entry.seq}`, turnKey: currentTurnKey, text: "Run failed" })
			}
		} else if (entry.type === "run_ended") {
			flushThoughts()
			items.push({
				kind: "notice",
				key: `n:${entry.seq}`,
				turnKey: currentTurnKey,
				text: END_NOTICES[entry.reason] ?? entry.reason,
			})
		}
	}

	// Render the streamed preview through the same ordered block path as its
	// durable replacement. Tool groups keep their call-id key across the swap.
	appendAssistantBlocks(conversation.partial ?? [], { provisional: true })
	flushThoughts()
	if (pending) {
		items.push({
			kind: "approval",
			key: `a:${pending.seq}`,
			turnKey: currentTurnKey,
			calls: pending.calls,
			seq: pending.seq,
		})
	}
	const filtered = items.filter((i) => i.kind !== "group" || i.steps.some((s) => s.call))
	const unsettledTurnKey = conversation.running || pending ? latestTurnKey : null

	// Only the terminal assistant message is the response. Earlier assistant
	// text is commentary and belongs inside the completed-work fold.
	const terminalTextByTurn = new Map()
	for (const item of filtered) {
		const turn = turns.get(item.turnKey)
		if (
			item.kind === "text" &&
			!item.provisional &&
			item.turnKey !== unsettledTurnKey &&
			turn?.terminalAssistant === item.entry
		) {
			const terminal = terminalTextByTurn.get(item.turnKey) ?? { items: [], text: [] }
			terminal.items.push(item)
			terminal.text.push(item.block.text)
			terminalTextByTurn.set(item.turnKey, terminal)
		}
	}
	const lastTerminalKeyByTurn = new Map(
		[...terminalTextByTurn].map(([turnKey, terminal]) => [turnKey, terminal.items.at(-1)?.key]),
	)
	const withCopyRows = []
	for (const item of filtered) {
		withCopyRows.push(item)
		if (lastTerminalKeyByTurn.get(item.turnKey) !== item.key) continue
		const terminal = terminalTextByTurn.get(item.turnKey)
		withCopyRows.push({
			kind: "turn-copy",
			key: `tc:${item.key}`,
			turnKey: item.turnKey,
			text: terminal.text.join("\n\n"),
			ts: item.entry?.ts ?? null,
		})
	}

	const foldableByTurn = new Map()
	for (const item of withCopyRows) {
		const turn = turns.get(item.turnKey)
		if (!turn?.hasUser || item.turnKey === unsettledTurnKey) continue
		const foldable =
			["group", "thinking", "compaction"].includes(item.kind) ||
			(item.kind === "text" && !item.provisional && item.entry !== turn.terminalAssistant)
		if (!foldable) continue
		const foldableItems = foldableByTurn.get(item.turnKey) ?? []
		foldableItems.push(item)
		foldableByTurn.set(item.turnKey, foldableItems)
	}

	const firstFoldableKeyByTurn = new Map(
		[...foldableByTurn].map(([turnKey, foldableItems]) => [turnKey, foldableItems[0].key]),
	)
	const foldableKeys = new Set([...foldableByTurn.values()].flat().map((item) => item.key))
	const result = []
	for (const item of withCopyRows) {
		if (firstFoldableKeyByTurn.get(item.turnKey) === item.key) {
			const turn = turns.get(item.turnKey)
			result.push({
				kind: "turn-fold",
				key: `tf:${item.turnKey}`,
				turnKey: item.turnKey,
				label: foldLabel(turn),
				expanded: expandedTurnKeys.has(item.turnKey),
			})
		}
		if (foldableKeys.has(item.key) && !expandedTurnKeys.has(item.turnKey)) continue
		result.push(item)
	}
	return result
}

function rawUserText(entry) {
	if (typeof entry?.content === "string") return entry.content
	return (entry?.content ?? [])
		.filter((block) => block.type === "text")
		.map((block) => block.text ?? "")
		.join("")
}

export function skillCommand(entry) {
	const invocation = parseSkillInvocation(rawUserText(entry))
	if (!invocation) return null
	return `/skill:${invocation.name}${invocation.instructions ? ` ${invocation.instructions}` : ""}`
}

// Pi and Tau persist skill expansions as ordinary user text and recover these
// presentation fields from the fixed wrapper when rendering history.
export function parseSkillInvocation(text) {
	const match = String(text ?? "").match(
		/^<skill name="([^"]+)" location="([^"]+)">\n([\s\S]*?)\n<\/skill>(?:\n\n([\s\S]+))?$/,
	)
	if (!match) return null
	return { name: match[1], location: match[2], content: match[3], instructions: match[4] ?? null }
}

// Mirror the server's strip + split(maxsplit=1) normalization for optimistic
// steering reconciliation. Unlike durable-event detection, this operates only on
// text the user explicitly entered as a slash command.
export function normalizeSkillCommand(text) {
	const match = String(text ?? "").trim().match(/^\/skill:([^\s]+)(?:\s+([\s\S]*))?$/)
	if (!match) return null
	const instructions = match[2]?.trim() || ""
	return `/skill:${match[1]}${instructions ? ` ${instructions}` : ""}`
}

export function userText(entry) {
	const text = rawUserText(entry)
	const invocation = parseSkillInvocation(text)
	if (!invocation) return text
	const label = `Using skill: ${invocation.name}`
	return invocation.instructions ? `${label}\n${invocation.instructions}` : label
}

export function userAttachments(entry) {
	return Array.isArray(entry?.content)
		? entry.content.filter((block) => block.type === "attachment")
		: []
}

export function conversationTitle(conversation) {
	const first = conversation.entries.find((e) => e.type === "user_message")
	if (!first) return null
	const raw = rawUserText(first)
	const invocation = parseSkillInvocation(raw)
	const titleText = invocation ? invocation.instructions || `/skill:${invocation.name}` : raw
	const line = titleText.split("\n")[0].trim() || userAttachments(first)[0]?.name || ""
	return line.length > 80 ? line.slice(0, 77) + "…" : line || null
}

// unix seconds → "14:32", with a date prefix once it's no longer today
export function formatTime(ts) {
	if (!ts) return ""
	const d = new Date(ts * 1000)
	const time = d.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })
	if (d.toDateString() === new Date().toDateString()) return time
	return `${d.toLocaleDateString([], { month: "short", day: "numeric" })}, ${time}`
}

export function formatTokens(n) {
	if (!n) return "0"
	if (n < 1000) return String(n)
	if (n < 1_000_000) return (n / 1000).toFixed(1).replace(/\.0$/, "") + "k"
	return (n / 1_000_000).toFixed(1).replace(/\.0$/, "") + "M"
}
