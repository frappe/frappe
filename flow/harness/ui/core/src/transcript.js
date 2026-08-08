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
		partialText: "",
		partialThinking: "",
		running: false,
		compacting: false,
		pendingApproval: null, // { seq, calls: [PendingCall], answers: {id: string} }
		model: null,
		reasoningEffort: null,
		usage: { input: 0, output: 0, cacheRead: 0, cacheWrite: 0, cost: 0 },
		contextTokens: 0,
		latestSeq: 0,
		lastError: null,
		liveLabel: null,
		needsReload: false,
		// errors witnessed live this page-load show in full; replayed ones are
		// just a marker (the store records which seqs arrived live)
		liveErrorSeqs: [],
	}
}

// Applies one wire event. Returns the state for chaining.
export function applyEvent(s, e) {
	if (typeof e.seq === "number") s.latestSeq = Math.max(s.latestSeq, e.seq)
	switch (e.type) {
		case "run_started":
			s.running = true
			s.lastError = null
			s.liveLabel = "Thinking…"
			s.pendingApproval = null // a new run consumes the batch (resume) — same as the server reducer
			break
		case "user_message":
		case "assistant_message":
		case "tool_result":
		case "compaction":
			if (e.type === "assistant_message") {
				s.partialText = ""
				s.partialThinking = ""
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
		case "approval_required":
			s.pendingApproval = { seq: e.seq, calls: e.calls, answers: {} }
			break
		case "run_ended":
			s.running = false
			s.liveLabel = null
			s.partialText = ""
			s.partialThinking = ""
			if (e.reason !== "paused") s.pendingApproval = null // a pause outlives its run
			// abnormal endings leave a durable marker in the transcript flow
			if (["aborted", "max_turns", "budget", "length"].includes(e.reason)) s.entries.push(e)
			break
		case "model_changed":
			s.model = e.model
			s.reasoningEffort = e.reasoning_effort ?? null
			break
		case "usage":
			s.usage.input += e.input_tokens ?? 0
			s.usage.output += e.output_tokens ?? 0
			s.usage.cacheRead += e.cache_read_tokens ?? 0
			s.usage.cacheWrite += e.cache_write_tokens ?? 0
			s.usage.cost += e.cost ?? 0
			if ((e.input_tokens ?? 0) + (e.output_tokens ?? 0) > 0)
				s.contextTokens = (e.input_tokens ?? 0) + (e.output_tokens ?? 0)
			break
		case "run_error":
			s.lastError = e
			s.entries.push(e) // rendered in place, and it survives a reload
			break
		case "rewind":
			// Entries before the target may be retracted; a full replay is the
			// only always-correct recovery. The store watches this flag.
			s.needsReload = true
			break
		case "text_delta":
			s.partialText += e.text
			s.liveLabel = null
			break
		case "thinking_delta":
			s.partialThinking += e.thinking
			// don't stomp a tool label — between tool calls the line stays put
			if (!s.liveLabel) s.liveLabel = "Thinking…"
			break
		case "tool_call_started":
			s.partialThinking = "" // the thought segment ended; it lands durably soon
			s.liveLabel = stepLabel(e.name) + "…"
			break
		case "retry":
			if (e.status === "started") {
				// the boundary where a failed attempt's deltas must be discarded.
				// liveLabel resets too: "Retrying…" must not stick through the new
				// attempt (thinking_delta only fills an empty label)
				s.partialText = ""
				s.partialThinking = ""
				s.liveLabel = null
			} else if (e.status === "scheduled") {
				s.liveLabel = "Retrying…"
			}
			break
		case "compaction_started":
			s.compacting = true
			s.liveLabel = "Compacting context…"
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
	return STEP_LABELS[name] ?? `Running ${name}`
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
	if (!d) return step.result ? "" : "…"
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

// Folds durable entries into renderable items:
//   {kind: "user", entry}
//   {kind: "text", block, entry}
//   {kind: "thinking", block, entry}
//   {kind: "group", steps: [{call, result, aborted} | {thought}]}
//   {kind: "approval", calls: [...], seq}      (undecided batch)
//   {kind: "compaction", entry}
//   {kind: "error", error}
// Every item carries a stable `key` (derived from seq / call id) so v-for
// state (expanded panels) survives the tail reshaping while streaming.
// Consecutive tool steps merge into one group; only a text/user item seals it.
// Thinking never splits a group: a thought adjacent to tool calls becomes a
// {thought} row inside the group, and stands alone only when no tools surround
// it (a pure thinking + text turn).
export function buildItems(conversation) {
	const items = []
	const stepsById = new Map()
	const pending = conversation.pendingApproval
	const pendingIds = new Set(pending?.calls.map((c) => c.id) ?? [])
	let bufferedThoughts = []

	const currentGroup = (firstCallId) => {
		const last = items[items.length - 1]
		if (last?.kind === "group") return last
		const group = { kind: "group", key: `g:${firstCallId}`, steps: [] }
		items.push(group)
		return group
	}
	// thoughts not claimed by a tool group render as standalone blocks
	const flushThoughts = () => {
		for (const t of bufferedThoughts) {
			items.push({ kind: "thinking", key: t.key, block: t.block, entry: t.entry })
		}
		bufferedThoughts = []
	}

	for (const entry of conversation.entries) {
		if (entry.type === "user_message") {
			flushThoughts()
			items.push({ kind: "user", key: `u:${entry.seq}`, entry })
		} else if (entry.type === "assistant_message") {
			let blockIdx = -1
			for (const block of entry.content ?? []) {
				blockIdx += 1
				if (block.type === "text" && block.text) {
					flushThoughts()
					items.push({ kind: "text", key: `t:${entry.seq}:${blockIdx}`, block, entry })
				} else if (block.type === "thinking") {
					const last = items[items.length - 1]
					if (last?.kind === "group") last.steps.push({ thought: block })
					else bufferedThoughts.push({ block, entry, key: `th:${entry.seq}:${blockIdx}` })
				} else if (block.type === "tool_call") {
					if (pendingIds.has(block.id)) continue // rendered as the approval card
					const group = currentGroup(block.id)
					for (const t of bufferedThoughts) group.steps.push({ thought: t.block })
					bufferedThoughts = []
					const step = { call: block, result: null, aborted: entry.stop_reason === "aborted" }
					stepsById.set(block.id, step)
					group.steps.push(step)
				}
			}
		} else if (entry.type === "tool_result") {
			const step = stepsById.get(entry.tool_call_id)
			if (step) step.result = entry
		} else if (entry.type === "compaction") {
			flushThoughts()
			items.push({ kind: "compaction", key: `c:${entry.seq}`, entry })
		} else if (entry.type === "run_error") {
			flushThoughts()
			if (conversation.liveErrorSeqs.includes(entry.seq)) {
				items.push({ kind: "error", key: `e:${entry.seq}`, error: entry })
			} else {
				items.push({ kind: "notice", key: `n:${entry.seq}`, text: "Run failed" })
			}
		} else if (entry.type === "run_ended") {
			flushThoughts()
			items.push({ kind: "notice", key: `n:${entry.seq}`, text: END_NOTICES[entry.reason] ?? entry.reason })
		}
	}

	flushThoughts()
	if (pending) {
		items.push({ kind: "approval", key: `a:${pending.seq}`, calls: pending.calls, seq: pending.seq })
	}
	const filtered = items.filter((i) => i.kind !== "group" || i.steps.some((s) => s.call))

	// one copy row per assistant turn, after the turn's LAST item (text, tools,
	// whatever an interrupted run left behind); the streaming turn gets its row
	// only once the run settles
	const result = []
	let turnTexts = []
	let copyKey = null
	let copyTs = null
	const flushCopy = () => {
		if (turnTexts.length) {
			result.push({ kind: "turn-copy", key: `tc:${copyKey}`, text: turnTexts.join("\n\n"), ts: copyTs })
		}
		turnTexts = []
	}
	for (const item of filtered) {
		if (item.kind === "user") {
			flushCopy()
			result.push(item)
		} else if (item.kind === "notice" || item.kind === "error") {
			flushCopy() // the copy row belongs to the content, above the marker
			result.push(item)
		} else {
			result.push(item)
			if (item.kind === "text") {
				turnTexts.push(item.block.text)
				copyKey = item.key
				copyTs = item.entry.ts ?? null
			}
		}
	}
	if (!conversation.running) flushCopy()
	return result
}

export function conversationTitle(conversation) {
	const first = conversation.entries.find((e) => e.type === "user_message")
	if (!first) return null
	const line = first.content.split("\n")[0].trim()
	return line.length > 80 ? line.slice(0, 77) + "…" : line
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
