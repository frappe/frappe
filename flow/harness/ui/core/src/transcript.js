// Pure event → view-model logic. Mirrors the server's reducer semantics
// (flow_tui/client/state.py is the reference): replay and live share one code
// path, durable entries rebuild everything, deltas are presentation-only.

export const EFFORTS = ["default", "off", "minimal", "low", "medium", "high", "xhigh", "max"]

// display names for the wire-level effort ids
// the two approval modes as the composer and the general settings present them
export const APPROVAL_MODES = [
	{ id: "ask", label: "Ask for approval", desc: "Asks before edits and commands." },
	{ id: "auto", label: "Auto-approve", desc: "Runs everything without asking." },
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

// words a model id spells its own way
const MODEL_WORDS = new Map(
	Object.entries({ gpt: "GPT", chatgpt: "ChatGPT", deepseek: "DeepSeek", glm: "GLM", oss: "OSS", minimax: "MiniMax", ai: "AI" }),
)

// A model's name for people: its provider's own where the list has one ("Anthropic: Claude Opus 4.5"),
// else its id spelled out ("codex/gpt-6-sol" → "GPT-6 Sol")
export function modelTitle(name, models = []) {
	const listed = models.find((model) => model.name === name)?.display_name
	if (listed) return listed
	const [id = "", variant] = (String(name ?? "").split("/").filter(Boolean).pop() ?? "").split(":")
	const words = []
	for (const part of id.split(/[-_\s]+/).filter(Boolean)) {
		const last = words.length - 1
		if (words[last] === "GPT" && /^\d/.test(part)) words[last] += `-${part}` // GPT-4o
		else if (/^\d$/.test(part) && /^\d$/.test(words[last])) words[last] += `.${part}` // claude-3-5 → 3.5
		else
			words.push(
				MODEL_WORDS.get(part.toLowerCase()) ??
					(/^o\d/.test(part) ? part // OpenAI's o3
					: /^[a-z]\d|^\d+(\.\d+)?b$/.test(part) ? part.toUpperCase() // V4.1, K2, 70B
					: part[0].toUpperCase() + part.slice(1)),
			)
	}
	const title = words.join(" ") || String(name ?? "")
	return variant ? `${title} (${variant})` : title
}

export function initialConversation() {
	return {
		entries: [],
		// messages the user has sent but the server has not echoed back yet: they
		// show as bubbles from the moment of sending, and the server's own copy
		// takes over when it lands in entries
		sending: [],
		// messages steered into the running turn that it has yet to take: bubbles below
		// it, as { key, entry, text, attachmentIds }, until the server's copy lands
		steering: [],
		// seqs of the messages steered into a run already under way: each joins that run's turn
		steeredSeqs: [],
		// where the current run's entries begin in `entries`
		runStart: 0,
		// Ordered, presentation-only assistant blocks accumulated from streaming
		// deltas. The terminal assistant_message atomically replaces this preview.
		partial: [],
		running: false,
		compacting: false, // or why: "manual", "threshold" or "overflow"
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
	return waitingApprovals(conversation)[0] ?? null
}

// every batch waiting on the user, in the order they are answered
export function waitingApprovals(conversation) {
	if (conversation.pendingApproval || !conversation.running)
		return conversation.pendingApproval ? [conversation.pendingApproval] : []
	const asked = Object.values(conversation.subagents ?? {})
		.map((child) => child.pendingApproval)
		.filter(Boolean)
	return asked.sort((a, b) => a.seq - b.seq)
}

// the tool a reply ends on to offer the user's next messages: chips, never a row
const SUGGEST_REPLIES = "suggest_replies"

// The next messages the latest reply offers, from its suggest_replies result, until the user
// says something: { key, replies, multiSelect }, else null
export function suggestedReplies(conversation) {
	if (conversation.running || conversation.pendingApproval || conversation.sending?.length) return null
	const entries = conversation.entries ?? []
	for (let i = entries.length - 1; i >= 0 && entries[i].type !== "user_message"; i--) {
		const { type, name, is_error, details, tool_call_id } = entries[i]
		if (type === "tool_result" && name === SUGGEST_REPLIES && !is_error && details?.replies)
			return { key: tool_call_id, replies: details.replies, multiSelect: !!details.multi_select }
	}
	return null
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
			s.runStart = s.entries.length
			break
		case "user_message":
		case "assistant_message":
		case "tool_result":
			if (e.type === "user_message") {
				s.liveLabel ??= "Working"
				// the server's copy of the oldest unechoed message: its bubble is real now
				s.sending.shift()
				// a run logs its own message first; one it takes after other rows was steered in
				if (s.running && s.entries.length > s.runStart) s.steeredSeqs.push(e.seq)
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
			s.compacting = false // a compaction never outlives its run, even one whose end went unseen
			if (e.reason !== "paused") s.pendingApproval = null // a pause outlives its run
			// abnormal endings leave a durable marker in the transcript flow
			if (["aborted", "max_turns", "budget", "length", "denied"].includes(e.reason))
				s.entries.push(e)
			// a sub-agent never outlives its session's run, not even one a crash cut off
			for (const child of Object.values(s.subagents ?? {}))
				Object.assign(child, { running: false, liveLabel: null, partial: [] })
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
				s.liveLabel = s.compacting ? "Compacting context" : "Working"
			} else if (e.status === "scheduled") {
				s.liveLabel = "Retrying"
			}
			break
		case "compaction_started":
			s.compacting = e.reason ?? true
			s.liveLabel = "Compacting context"
			break
		case "compaction_ended":
			s.compacting = false
			// a run that compacted to make room goes on working; a /compact ends here
			s.liveLabel = s.running && e.reason !== "manual" ? "Working" : null
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
	s.requests.push(e) // whole: the transcript shows the report itself
}

const END_NOTICES = {
	aborted: "Interrupted by user",
	denied: "Tool call denied by user",
	max_turns: "Stopped — turn limit reached",
	budget: "Stopped — token budget reached",
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

function deriveTurns(entries, steeredSeqs = []) {
	const turns = new Map()
	const turnByEntry = new Map()
	let current = null

	for (const [index, entry] of entries.entries()) {
		// a steered message joins the turn it was steered into: one fold, one copy row
		if (entry.type === "user_message" && !(current && steeredSeqs.includes(entry.seq))) {
			current = {
				key: `turn:${entry.seq ?? index}`,
				hasUser: true,
				startedAt: Number.isFinite(entry.ts) ? entry.ts : null,
				endedAt: Number.isFinite(entry.ts) ? entry.ts : null,
				stopped: false,
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
				stopped: false,
				interrupted: false,
			}
			turns.set(current.key, current)
		}

		if (!current) continue
		turnByEntry.set(entry, current.key)
		// a compaction joins the turn before it, but a later /compact is no time it worked
		if (Number.isFinite(entry.ts) && entry.type !== "compaction") {
			current.endedAt = current.endedAt == null ? entry.ts : Math.max(current.endedAt, entry.ts)
		}
		if (entry.type === "run_ended" && entry.reason === "aborted") current.interrupted = true
		// a user-terminated turn (abort/deny) has no response: its last text folds with the work
		if (entry.type === "run_ended" && ["aborted", "denied"].includes(entry.reason)) current.stopped = true
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
	const { turns, turnByEntry, latestTurnKey } = deriveTurns(conversation.entries, conversation.steeredSeqs)
	let currentTurnKey = null
	let bufferedThoughts = []
	// a thought or text has no wire id, so its turn and ordinal name it across the preview's durable swap
	let thoughtCount = 0
	let textCount = 0

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
					: `${currentTurnKey}:tx:${textCount}`
			if (block.type === "text" && block.text.trim()) {
				flushThoughts()
				textCount++
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
				if (block.name === SUGGEST_REPLIES) continue // shown as chips, not a row
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
	// A message in flight opens a new turn (a steered one joins the running turn instead), and
	// settles the one before it right away: its run_started lands before the server's copy
	// of the message, and reading that as the old turn resuming unfolds a finished turn.
	const opensNewTurn = (conversation.sending ?? []).length > 0
	// a /compact runs after the latest turn ended: that turn stays settled while it does
	const unsettledTurnKey =
		!opensNewTurn && (conversation.running || pending) && conversation.compacting !== "manual"
			? latestTurnKey
			: null

	// A turn's response is its last text and everything after it; earlier text is commentary
	// and folds with the work. A turn the user stopped or denied has none, the running one none yet.
	const responseStart = new Map()
	for (const [index, item] of filtered.entries()) {
		const turn = turns.get(item.turnKey)
		if (item.kind === "text" && !item.provisional && item.turnKey !== unsettledTurnKey && turn && !turn.stopped)
			responseStart.set(item.turnKey, index)
	}
	for (const [turnKey, index] of responseStart) {
		let start = index // texts in a row are one
		while (filtered[start - 1]?.kind === "text" && filtered[start - 1].turnKey === turnKey) start--
		responseStart.set(turnKey, start)
	}
	const inResponse = new Set(
		filtered.filter((item, index) => index >= (responseStart.get(item.turnKey) ?? Infinity)).map((item) => item.key),
	)
	const terminalTextByTurn = new Map()
	for (const item of filtered) {
		if (item.kind !== "text" || !inResponse.has(item.key)) continue
		const terminal = terminalTextByTurn.get(item.turnKey) ?? { items: [], text: [] }
		terminal.items.push(item)
		terminal.text.push(item.block.text)
		terminalTextByTurn.set(item.turnKey, terminal)
	}
	// the files card and the copy/time row close the turn, below all it shows but a later compaction
	const lastKeyByTurn = new Map(
		filtered.filter((item) => item.kind !== "compaction").map((item) => [item.turnKey, item.key]),
	)
	const fileChangesByTurn = deriveFileChanges(conversation.entries, turnByEntry)
	const withCopyRows = []
	for (const item of filtered) {
		withCopyRows.push(item)
		const terminal = terminalTextByTurn.get(item.turnKey)
		if (!terminal || lastKeyByTurn.get(item.turnKey) !== item.key) continue
		const changed = fileChangesByTurn.get(item.turnKey)
		if (changed?.size) {
			withCopyRows.push({
				kind: "turn-files",
				key: `tfs:${item.turnKey}`,
				turnKey: item.turnKey,
				files: [...changed.values()],
			})
		}
		const response = terminal.items.at(-1)
		withCopyRows.push({
			kind: "turn-copy",
			key: `tc:${response.key}`,
			turnKey: item.turnKey,
			text: terminal.text.join("\n\n"),
			ts: response.entry?.ts ?? null,
		})
	}

	const foldableByTurn = new Map()
	for (const item of withCopyRows) {
		const turn = turns.get(item.turnKey)
		if (!turn?.hasUser || item.turnKey === unsettledTurnKey) continue
		const foldable =
			item.kind === "compaction" ||
			(!inResponse.has(item.key) &&
				(["group", "thinking"].includes(item.kind) || (item.kind === "text" && !item.provisional)))
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
	// a steered message waits last: below the turn it joined, which goes on above it, or
	// below the message still on its way whose run it joins
	for (const message of [...(conversation.sending ?? []), ...(conversation.steering ?? [])]) {
		result.push({ kind: "user", key: message.key, turnKey: null, entry: message.entry })
	}
	return result
}

// One row per operation, in transcript order, holding the objects the server sent
// minus Flow's own fields. Usage belongs to model requests, so attach each provider
// report to the row that made the call — a response, or a compaction — never to
// messages or tool results. A sub-agent call's row sums what its child spent.
//   {key, kind: "system"|"user"|"assistant"|"tool"|"compaction"|"error",
//    body?, entry?, input?, output?, usage?}
export function buildTranscriptRows(conversation) {
	const rows = []
	const steps = new Map() // tool call id -> its row, filled when the result lands
	const runs = new Map() // sub-agent call id -> its child and the log span it ran in
	const entries = conversation.entries ?? []
	const requests = conversation.requests ?? []
	let cursor = 0

	// the system prompt opens every request; its text stays out of the log
	if (entries.length) {
		rows.push({ key: "system", kind: "system", body: "System prompt." })
	}

	for (const [index, entry] of entries.entries()) {
		let caller = null // the row whose model call a usage report in this gap belongs to
		if (entry.type === "user_message") {
			rows.push({ key: `u:${entry.seq}`, kind: "user", entry: withoutFlowFields(entry) })
		} else if (entry.type === "assistant_message") {
			caller = { key: `a:${entry.seq}`, kind: "assistant", entry: withoutFlowFields(entry) }
			rows.push(caller)
			// each call is its tool's input; the result lands as its output
			for (const call of entry.content.filter((block) => block.type === "tool_call")) {
				const step = { key: `c:${call.id}`, kind: "tool", input: withoutFlowFields(call) }
				steps.set(call.id, step)
				rows.push(step)
				const child = call.name === "subagent" ? conversation.subagents?.[subagentId(call)] : null
				if (child) runs.set(call.id, { step, child, from: entry.seq, to: Infinity })
			}
		} else if (entry.type === "tool_result") {
			const step = steps.get(entry.tool_call_id)
			if (step) step.output = withoutFlowFields(entry)
			const run = runs.get(entry.tool_call_id)
			if (run) run.to = entry.seq
		} else if (entry.type === "compaction") {
			caller = { key: `k:${entry.seq}`, kind: "compaction", entry: withoutFlowFields(entry) }
			rows.push(caller)
		} else if (entry.type === "run_error") {
			rows.push({ key: `e:${entry.seq}`, kind: "error", entry: withoutFlowFields(entry) })
		}

		// Usage normally follows its assistant message or compaction immediately.
		const until = entries[index + 1]?.seq ?? Infinity
		while (cursor < requests.length && requests[cursor].seq < until) {
			const usage = requests[cursor++]
			if (caller && !caller.usage && (caller.kind === "compaction") === !!usage.standalone)
				caller.usage = withoutFlowFields(usage)
		}
	}
	// a continued sub-agent runs once per call: each row counts only its own run
	for (const { step, child, from, to } of runs.values()) {
		const reports = child.requests.filter((usage) => usage.seq > from && usage.seq < to)
		if (reports.length) step.usage = summedUsage(reports)
	}
	return rows
}

// usage reports added up, in the fields one report has
function summedUsage(reports) {
	const fields = ["input_tokens", "output_tokens", "cache_read_tokens", "cache_write_tokens", "cost"]
	return Object.fromEntries(fields.map((field) => [field, reports.reduce((sum, usage) => sum + (usage[field] ?? 0), 0)]))
}

// Flow's bookkeeping: the log's envelope, render hints, adapter state, accounting flags
const FLOW_FIELDS = new Set([
	"seq",
	"parent_seq",
	"ts",
	"subagent_id",
	"api",
	"display",
	"details",
	"provider_state",
	"standalone",
	"context_window",
	"compact_up_to_seq",
])

// an entry or content block without Flow's fields; tool arguments stay as the model wrote them
function withoutFlowFields(object) {
	return Object.fromEntries(
		Object.entries(object)
			.filter(([key]) => !FLOW_FIELDS.has(key))
			.map(([key, value]) => [key, key === "content" && Array.isArray(value) ? value.map(withoutFlowFields) : value]),
	)
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
	return invocation && typedCommand(invocation.names[0], invocation.instructions)
}

// the skills a message brought in, or null when it brought in none
export function invokedSkills(entry) {
	return parseSkillInvocation(rawUserText(entry))?.names ?? null
}

// "/skill:<name>" as a word of its own, anywhere in a message; no lookbehind, which
// Safari before 16.4 can't parse
const SKILL_TOKEN = /(^|\s)\/skill:(\S+)/g
const SKILL_BLOCK = /<skill name="([^"]+)" location="([^"]+)">\n[\s\S]*?\n<\/skill>(?:\n\n|$)/y

// Pi and Tau persist skill expansions as ordinary user text and recover these
// presentation fields from the fixed wrapper when rendering history; one block per skill.
export function parseSkillInvocation(text) {
	const source = String(text ?? "")
	const names = []
	let end = 0
	for (;;) {
		SKILL_BLOCK.lastIndex = end
		const match = SKILL_BLOCK.exec(source)
		if (!match) break
		names.push(match[1])
		end = SKILL_BLOCK.lastIndex
	}
	return names.length ? { names, instructions: source.slice(end) || null } : null
}

// the message as typed: a leading command gave way to its skill, a later one stayed
function typedCommand(name, instructions) {
	if (instructions && skillTokens(instructions).some((token) => token.name === name)) return instructions
	return `/skill:${name}${instructions ? ` ${instructions}` : ""}`
}

// the skill commands typed in `text`; a quoted line ("> …") starts nothing
function skillTokens(text) {
	const tokens = []
	for (const match of text.matchAll(SKILL_TOKEN)) {
		const start = match.index + match[1].length
		if (text[text.lastIndexOf("\n", start - 1) + 1] === ">") continue
		tokens.push({ start, end: match.index + match[0].length, name: match[2] })
	}
	return tokens
}

// Mirror the server's strip + split(maxsplit=1) normalization for optimistic
// steering reconciliation. Unlike durable-event detection, this operates only on
// text the user explicitly entered as a slash command.
export function normalizeSkillCommand(text) {
	const trimmed = String(text ?? "").trim()
	const match = trimmed.match(/^\/skill:([^\s]+)(?:\s+([\s\S]*))?$/)
	if (!match) return null
	const rest = match[2]?.trim() || ""
	// named again later, the server keeps the text as typed
	if (skillTokens(rest).some((token) => token.name === match[1])) return trimmed
	return `/skill:${match[1]}${rest ? ` ${rest}` : ""}`
}

// text split around the skill commands among `names`, so they can show in blue
export function skillSegments(text, names) {
	const parts = []
	let end = 0
	for (const token of skillTokens(text)) {
		if (!names.includes(token.name)) continue
		if (token.start > end) parts.push({ text: text.slice(end, token.start), skill: false })
		parts.push({ text: text.slice(token.start, token.end), skill: true })
		end = token.end
	}
	if (end < text.length) parts.push({ text: text.slice(end), skill: false })
	return parts
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

const QUOTE_LINE = /^> ?(.*)$/

// a thread selection added to chat travels as a blockquote under the message
export function quoteBlock(text) {
	return text.split("\n").map((line) => (line ? `> ${line}` : ">")).join("\n")
}

// split those blockquotes back out so a bubble can show them as quotes
export function splitQuotes(text) {
	const paragraphs = String(text ?? "").split("\n\n")
	const quotes = []
	while (paragraphs.length && paragraphs.at(-1).split("\n").every((line) => QUOTE_LINE.test(line))) {
		quotes.unshift(paragraphs.pop().split("\n").map((line) => line.replace(QUOTE_LINE, "$1")).join("\n"))
	}
	return { body: paragraphs.join("\n\n"), quotes }
}

export function conversationTitle(conversation) {
	const first =
		conversation.entries.find((e) => e.type === "user_message") ?? conversation.sending?.[0]?.entry
	if (!first) return null
	const raw = rawUserText(first)
	const command = skillCommand(first) ?? normalizeSkillCommand(raw)
	const titleText = command ? command.replace(/^\/skill:\S+\s*/, "") || command : raw
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
