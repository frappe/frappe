// Pure event → view-model logic. Mirrors the server's reducer semantics
// (flow_tui/client/state.py is the reference): replay and live share one code
// path, durable entries rebuild everything, deltas are presentation-only.

export const EFFORTS = ["default", "off", "minimal", "low", "medium", "high", "xhigh", "max"]

// display names for the wire-level effort ids
// the two approval modes as the composer and the general settings present them
export const APPROVAL_MODES = [
	{ id: "ask", label: "Ask for approval", desc: "Pauses before writes, edits and commands." },
	{ id: "auto", label: "Auto-approve", desc: "Runs every tool without stopping to ask." },
]

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
		// messages the user has sent but the server has not echoed back yet: they
		// show as bubbles from the moment of sending, and the server's own copy
		// takes over when it lands in entries
		sending: [],
		// Ordered, presentation-only assistant blocks accumulated from streaming
		// deltas. The terminal assistant_message atomically replaces this preview.
		partial: [],
		running: false,
		compacting: false,
		pendingApproval: null, // { seq, calls: [PendingCall], answers: {id: string}, subagentId? }
		// the sub-agents this conversation started, by id: each a conversation of its own
		subagents: {},
		model: null,
		reasoningEffort: null,
		usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0 },
		// one record per model request, in log order, for the per-step token view
		requests: [],
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
	return e.subagent_id ? applySubagentEvent(s, e) : foldEvent(s, e)
}

// A sub-agent's event folds into the child's own conversation; the session keeps
// only its cost, and answers the question a paused child asks (approvalToAnswer).
function applySubagentEvent(s, e) {
	if (typeof e.seq === "number") s.latestSeq = Math.max(s.latestSeq, e.seq)
	const child = (s.subagents[e.subagent_id] ??= initialConversation())
	foldEvent(child, e)
	if (e.type === "usage") addUsage(s, e)
	else if (e.type === "approval_required") child.pendingApproval.subagentId = e.subagent_id
	return s
}

// the batch to answer: the session's own, else the oldest a sub-agent waits on while
// the session runs (the session's run ending takes its children's questions with it)
export function approvalToAnswer(conversation) {
	if (conversation.pendingApproval || !conversation.running) return conversation.pendingApproval ?? null
	const asked = Object.values(conversation.subagents ?? {})
		.map((child) => child.pendingApproval)
		.filter(Boolean)
	return asked.sort((a, b) => a.seq - b.seq)[0] ?? null
}

function foldEvent(s, e) {
	if (typeof e.seq === "number") s.latestSeq = Math.max(s.latestSeq, e.seq)
	switch (e.type) {
		case "run_started":
			s.running = true
			s.lastError = null
			s.liveLabel = "Working"
			s.partial = []
			s.pendingApproval = null // a new run consumes the batch (resume) — same as the server reducer
			break
		case "user_message":
		case "assistant_message":
		case "tool_result":
			if (e.type === "user_message") {
				s.liveLabel ??= "Working"
				// the server's copy of the oldest unechoed message: its bubble is real now
				s.sending.shift()
			}
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
			if (["aborted", "max_turns", "budget", "length", "denied"].includes(e.reason))
				s.entries.push(e)
			break
		case "model_changed":
			if (s.model !== e.model) s.contextWindow = null
			s.model = e.model
			s.reasoningEffort = e.reasoning_effort ?? null
			s.contextTokens = 0
			break
		case "usage":
			addUsage(s, e)
			recordRequest(s, e)
			if (e.context_window != null) s.contextWindow = e.context_window
			// the summarizer's own call prompts with its own text: spend, not context
			if (!e.standalone && (e.input_tokens ?? 0) + (e.output_tokens ?? 0) > 0)
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
		case "preview_replay_started":
			s.partial = []
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
			// Arguments can stream for a while (write/edit payloads), and the row
			// renders only on tool_call_display_ready — a generic status covers that
			// gap. Tool names belong to the rows, never to the status line.
			s.liveLabel = "Working"
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
			s.liveLabel = "Working"
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

function addUsage(s, e) {
	s.usage.input += e.input_tokens ?? 0
	s.usage.output += e.output_tokens ?? 0
	s.usage.cacheRead += e.cache_read_tokens ?? 0
	s.usage.cacheWrite += e.cache_write_tokens ?? 0
	s.usage.cost += e.cost ?? 0
}

function recordRequest(s, e) {
	// a cancelled turn reports an empty Usage(): no numbers to show, no call to count
	if (!(e.input_tokens ?? 0) && !(e.output_tokens ?? 0)) return
	s.requests.push({
		seq: e.seq ?? 0,
		input: e.input_tokens ?? 0,
		output: e.output_tokens ?? 0,
		cacheRead: e.cache_read_tokens ?? 0,
		cacheWrite: e.cache_write_tokens ?? 0,
		cost: e.cost ?? 0,
		standalone: e.standalone ?? false,
	})
}

const END_NOTICES = {
	aborted: "Interrupted by user",
	denied: "Tool call denied by user",
	max_turns: "Stopped — turn limit reached",
	budget: "Stopped — output budget reached",
	length: "Stopped — model hit its length limit",
}

const STEP_LABELS = {
	subagent: "Sub-agent",
	read: "Reading file",
	grep: "Searching code",
	bash: "Running command",
	edit: "Editing file",
	write: "Writing file",
}

export function stepLabel(name) {
	return STEP_LABELS[name] ?? humanizeToolName(name)
}

// Leading row icons for the built-in tools; extension tools get the generic wrench.
const STEP_ICONS = {
	subagent: "bot",
	read: "file-text",
	grep: "search",
	bash: "terminal",
	edit: "edit-3",
	write: "file-plus",
	websearch: "globe",
}

export function stepIcon(name) {
	return STEP_ICONS[name] ?? "tool"
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

export function fileName(path) {
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
		if (["read", "write", "edit"].includes(name))
			return call.display
				.map((segment) => (segment.arg === "path" ? fileName(segment.text) : segment.text))
				.join("")
		return displayText(call.display)
	}
	const label = stepLabel(name)
	if (["read", "write", "edit"].includes(name)) {
		const subject = fileName((call.arguments ?? call.args ?? {}).path)
		return subject ? `${label} ${subject}` : label
	}
	if (name in STEP_LABELS) return label
	return `Running ${lowerFirst(label)}`
}

// Display-only compaction for tool row argument text: cwd-relative paths,
// no `cd <cwd> && ` command prefix, `~` for the home directory. Expanded
// panels and copy actions keep the full text.
export function compactDisplayText(text, cwd) {
	let value = String(text ?? "")
	cwd = cwd ? String(cwd).replace(/\/+$/, "") : cwd
	if (cwd) {
		if (value === cwd) return "."
		const cd = `cd ${cwd} && `
		if (value.startsWith(cd)) value = value.slice(cd.length)
		if (value.startsWith(cwd + "/")) value = value.slice(cwd.length + 1)
		else value = value.split(cwd + "/").join("")
	}
	return value.replace(/(^|[\s"'=(])\/(?:Users|home)\/[^/\s"']+/g, "$1~")
}

// The one-line summary shown next to a step label.
export function stepSubject(call) {
	const a = call.arguments ?? call.args ?? {}
	switch (call.name) {
		case "read":
		case "write":
			return a.path ?? ""
		case "edit":
			return a.path ?? ""
		case "grep":
			return a.pattern ?? ""
		case "bash":
			return a.command ?? ""
		case "subagent":
			return a.description ?? ""
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
	// a stopped sub-agent says why; a finished one names its agent, unless it was the default
	if (d.end_reason !== undefined) {
		if (d.end_reason !== "done") return d.end_reason.replace("_", " ")
		return d.agent === "general" ? "" : d.agent
	}
	if (d.matches !== undefined) return `${d.matches} matches`
	if (d.lines_added !== undefined || d.lines_removed !== undefined)
		return `+${d.lines_added ?? 0} -${d.lines_removed ?? 0}`
	if (d.edits !== undefined) return `${d.edits} edits`
	if (d.lines !== undefined) return `${d.lines} lines`
	if (d.total_lines !== undefined) return `${d.total_lines} lines`
	if (d.chars !== undefined) return `${d.chars} chars`
	return ""
}

// the child a subagent call runs: the one it continues, else the one it starts, named by the call
export function subagentId(call) {
	return (call.arguments ?? call.args ?? {}).subagent_id || call.id
}

// what the session called a sub-agent: the description of the call that started it
export function subagentTitle(conversation, id) {
	const isCall = (block) => block.type === "tool_call" && block.id === id
	for (const entry of conversation.entries) {
		if (entry.type !== "assistant_message") continue
		const call = (entry.content ?? []).find(isCall)
		if (call) return call.arguments?.description ?? null
	}
	return conversation.partial.find(isCall)?.arguments?.description ?? null // still streaming
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
		// a user-terminated turn (abort/deny) has no terminal response: its last
		// text folds with the work instead of standing as the answer
		if (entry.type === "run_ended" && ["aborted", "denied"].includes(entry.reason))
			current.terminalAssistant = null
	}

	return { turns, turnByEntry, latestTurnKey: [...turns.keys()].at(-1) ?? null }
}

// Files touched by a turn's settled edit/write calls, keyed by turn, aggregated
// per path in first-touch order. Denied/failed calls don't count; a write
// reports its full line count as additions.
function deriveFileChanges(entries, turnByEntry) {
	const callTurns = new Map()
	const filesByTurn = new Map()
	for (const entry of entries) {
		if (entry.type === "assistant_message") {
			for (const block of entry.content ?? []) {
				if (block.type === "tool_call" && ["edit", "write"].includes(block.name))
					callTurns.set(block.id, turnByEntry.get(entry))
			}
		} else if (entry.type === "tool_result" && callTurns.has(entry.tool_call_id)) {
			const path = entry.details?.path
			if (!path || entry.is_error || stepDecision(entry)) continue
			const turnKey = callTurns.get(entry.tool_call_id)
			const files = filesByTurn.get(turnKey) ?? new Map()
			const file = files.get(path) ?? { path, added: 0, removed: 0 }
			file.added += entry.details.lines_added ?? entry.details.lines ?? 0
			file.removed += entry.details.lines_removed ?? 0
			files.set(path, file)
			filesByTurn.set(turnKey, files)
		}
	}
	return filesByTurn
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
//   {kind: "group", steps: [{call, result, aborted} | {thought, id, live?}]}
//   {kind: "turn-fold", turnKey, label, expanded}
//   {kind: "turn-files", turnKey, files: [{path, added, removed}]}
//   {kind: "compaction", entry}
//   {kind: "error", error}
// Every item carries a stable `key` (derived from seq / call id) so v-for
// state (expanded panels) survives the tail reshaping while streaming.
// Consecutive tool steps merge into one group; only a text/user item seals it.
// Thinking never splits a group: a thought adjacent to tool calls becomes a
// {thought} row inside the group, and stands alone only when no tools surround
// it (a pure thinking + text turn).
export function buildItems(conversation, expandedTurnKeys = new Set(), openPanels = new Set()) {
	const items = []
	const stepsById = new Map()
	const pending = conversation.pendingApproval
	const pendingIds = new Set(pending?.calls.map((c) => c.id) ?? [])
	const { turns, turnByEntry, latestTurnKey } = deriveTurns(conversation.entries)
	let currentTurnKey = null
	let bufferedThoughts = []
	// a thought has no wire id, so its turn and ordinal name it across the preview's durable swap
	let thoughtCount = 0

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
		// a thought is live only while its chunks are still arriving — i.e. while it
		// is the newest streamed block. Any block after it (a tool call, text) means
		// that thought ended: it settles to "Thought" and the status line takes over.
		const lastLiveIdx = provisional ? blocks.length - 1 : -1
		for (const [blockIdx, block] of blocks.entries()) {
			// only a thought with text takes an ordinal: the preview never streams a text-less block
			const key =
				block.type === "thinking"
					? block.thinking
						? `${currentTurnKey}:th:${thoughtCount++}`
						: `th:${entry.seq}:${blockIdx}`
					: provisional
						? `p:${blockIdx}`
						: `t:${entry.seq}:${blockIdx}`
			if (block.type === "text" && block.text.trim()) {
				flushThoughts()
				items.push({ kind: "text", key, turnKey: currentTurnKey, block, entry, provisional })
			} else if (block.type === "thinking") {
				const last = items[items.length - 1]
				if (last?.kind === "group")
					last.steps.push({ thought: block, id: key, live: provisional && blockIdx === lastLiveIdx })
				else {
					bufferedThoughts.push({
						block,
						entry,
						key,
						turnKey: currentTurnKey,
						live: provisional && blockIdx === lastLiveIdx,
					})
				}
			} else if (block.type === "tool_call") {
				if (provisional && block.arguments == null) continue
				if (pendingIds.has(block.id) || stepsById.has(block.id)) continue
				const group = currentGroup(block.id)
				for (const thought of bufferedThoughts) group.steps.push({ thought: thought.block, id: thought.key })
				bufferedThoughts = []
				const step = {
					call: block,
					result: null,
					aborted: !provisional && entry.stop_reason === "aborted",
					// a subagent call's child, once its first event has landed
					subagent: block.name === "subagent" ? conversation.subagents?.[subagentId(block)] ?? null : null,
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
	const filtered = items.filter((i) => i.kind !== "group" || i.steps.some((s) => s.call))
	// A message in flight opens a new turn (steering queues in the composer instead), and
	// settles the one before it right away: its run_started lands before the server's copy
	// of the message, and reading that as the old turn resuming unfolds a finished turn.
	const opensNewTurn = (conversation.sending ?? []).length > 0
	const unsettledTurnKey = !opensNewTurn && (conversation.running || pending) ? latestTurnKey : null

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
	const fileChangesByTurn = deriveFileChanges(conversation.entries, turnByEntry)
	const withCopyRows = []
	for (const item of filtered) {
		withCopyRows.push(item)
		if (lastTerminalKeyByTurn.get(item.turnKey) !== item.key) continue
		const terminal = terminalTextByTurn.get(item.turnKey)
		// the files card folds into the response; the copy/time row closes the turn
		const changed = fileChangesByTurn.get(item.turnKey)
		if (changed?.size) {
			withCopyRows.push({
				kind: "turn-files",
				key: `tfs:${item.turnKey}`,
				turnKey: item.turnKey,
				files: [...changed.values()],
			})
		}
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
	// a fold never hides a row the user has open: that turn stays unfolded
	const expandedTurns = new Set(expandedTurnKeys)
	for (const [turnKey, foldableItems] of foldableByTurn) {
		if (foldableItems.some((item) => panelIds(item).some((id) => openPanels.has(id)))) expandedTurns.add(turnKey)
	}
	const result = []
	for (const item of withCopyRows) {
		if (firstFoldableKeyByTurn.get(item.turnKey) === item.key) {
			const turn = turns.get(item.turnKey)
			result.push({
				kind: "turn-fold",
				key: `tf:${item.turnKey}`,
				turnKey: item.turnKey,
				label: foldLabel(turn),
				expanded: expandedTurns.has(item.turnKey),
			})
		}
		if (foldableKeys.has(item.key) && !expandedTurns.has(item.turnKey)) continue
		result.push(item)
	}
	for (const message of conversation.sending ?? []) {
		result.push({ kind: "user", key: message.key, turnKey: null, entry: message.entry })
	}
	return result
}

// One row per operation, in transcript order. Usage belongs to model requests,
// so attach each provider report to the row that made the call — a response, or
// a compaction — rather than attributing its input to messages or tool results.
//   {key, kind: "system"|"user"|"assistant"|"tool"|"compaction"|"error",
//    body, subject?, thinking?, name?, input?, output?, failed?, request?, spent?}
export function buildTranscriptRows(conversation) {
	const rows = []
	const steps = new Map() // tool call id -> its row, filled when the result lands
	const entries = conversation.entries ?? []
	const requests = conversation.requests ?? []
	let cursor = 0

	// the system prompt opens every request; its text stays out of the log
	if (entries.length) {
		rows.push({ key: "system", kind: "system", subject: "", body: "System prompt." })
	}

	for (const [index, entry] of entries.entries()) {
		let caller = null // the row whose model call a usage report in this gap belongs to
		if (entry.type === "user_message") {
			// an image-only message has no text at all: its attachments name the row
			const names = userAttachments(entry).map((item) => item.name).join(", ")
			rows.push({ key: `u:${entry.seq}`, kind: "user", subject: names, body: userText(entry) })
		} else if (entry.type === "assistant_message" && entry.content?.length) {
			// an aborted turn can leave a message with no blocks at all: nothing to show
			caller = assistantRow(entry)
			rows.push(caller)
			for (const call of entry.content.filter((block) => block.type === "tool_call")) {
				const step = toolRow(call, conversation)
				steps.set(call.id, step)
				rows.push(step)
			}
		} else if (entry.type === "tool_result") {
			const step = steps.get(entry.tool_call_id)
			if (step) {
				step.output = entry.content ?? ""
				step.failed = entry.is_error === true
			}
		} else if (entry.type === "compaction") {
			caller = {
				key: `k:${entry.seq}`,
				kind: "compaction",
				subject: "everything before this is now a summary",
				body: entry.summary ?? "",
			}
			rows.push(caller)
		} else if (entry.type === "run_error") {
			rows.push({ key: `e:${entry.seq}`, kind: "error", subject: entry.message ?? "", body: entry.detail ?? "" })
		}

		// Usage normally follows its assistant message or compaction immediately.
		const until = entries[index + 1]?.seq ?? Infinity
		while (cursor < requests.length && requests[cursor].seq < until) {
			const request = requests[cursor++]
			if (caller && !caller.request && (caller.kind === "compaction") === request.standalone)
				caller.request = request
		}
	}
	return rows
}

function assistantRow(entry) {
	const blocks = entry.content ?? []
	const join = (type, field) => blocks.filter((b) => b.type === type).map((b) => b[field]).join("\n\n")
	return {
		key: `a:${entry.seq}`,
		kind: "assistant",
		subject: "",
		thinking: join("thinking", "thinking"),
		body: join("text", "text"),
	}
}

function toolRow(call, conversation) {
	// a sub-agent's own spend never enters this context: report it beside the row
	const child = call.name === "subagent" ? conversation.subagents?.[subagentId(call)] : null
	// every tool reads the same way, built-in or not: what it was called with,
	// then what it returned — no per-tool summary of a chosen argument
	const args = call.arguments ?? call.args ?? {}
	return {
		key: `c:${call.id}`,
		kind: "tool",
		name: call.name,
		input: Object.keys(args).length ? JSON.stringify(args, null, 2) : "",
		output: "",
		failed: false,
		spent: child ? child.usage.input + child.usage.output : 0,
	}
}

// ids of the rows an item can expand: its tool calls and thoughts
export function panelIds(item) {
	if (item.kind === "group") return item.steps.map((step) => step.call?.id ?? step.id)
	return item.kind === "thinking" ? [item.key] : []
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

// a skill the user started shows as the command they typed, never its expansion
export function userText(entry) {
	return skillCommand(entry) ?? rawUserText(entry)
}

export function userAttachments(entry) {
	return Array.isArray(entry?.content)
		? entry.content.filter((block) => block.type === "attachment")
		: []
}

const CODE_REF_LINE = /^@(.+):(\d+)(?:-(\d+))?$/

// "Add to chat" selections travel as @path:start-end lines appended to the message;
// split them back out so a bubble can show chips instead of the raw tokens
export function splitCodeRefs(text) {
	const lines = String(text ?? "").split("\n")
	const refs = []
	while (lines.length) {
		const match = CODE_REF_LINE.exec(lines[lines.length - 1].trim())
		if (!match) break
		lines.pop()
		refs.unshift({ path: match[1], start: Number(match[2]), end: Number(match[3] ?? match[2]) })
	}
	return { body: lines.join("\n").trimEnd(), refs }
}

export function codeRefLabel(ref) {
	return `${fileName(ref.path)} (${ref.start}${ref.end !== ref.start ? `-${ref.end}` : ""})`
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
