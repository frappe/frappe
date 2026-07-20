import { ref, computed } from "vue";
import * as api from "@/api/client";
import { startRun, resumeRun } from "@/api/stream";
import { normalizeToolName } from "@/lib/toolMeta";
import { readPanelState } from "@/lib/panelState";
import { __ } from "@/lib/translate";

// Module-singleton store: one panel instance, one source of truth. Components
// import this and read/act on shared reactive state — no prop drilling.

let uid = 0;
const nextId = () => `n${++uid}`;
let auid = 0;
const nextAttachmentId = () => `a${++auid}`;

// ── state ───────────────────────────────────────────────────────────────────
const agents = ref([]);
const models = ref([]);
const recentSessions = ref([]);

// Active agent's tool slug → requires_confirmation; the cache keeps agent switches instant.
const toolApproval = ref({});
const toolApprovalCache = {};

const selectedAgent = ref(null);
const selectedModel = ref(null);
const sessionName = ref(null);
const runName = ref(null);

const messages = ref([]);
// Composer attachments staged for the next turn: { uid, file, file_name, file_size, status, error }.
// status: "uploading" | "ready" | "error".
const attachments = ref([]);
const sending = ref(false);
const loaded = ref(false);
const fullscreen = ref(false);

// Bumped whenever new content arrives / focus is wanted; views watch & react.
const scrollTick = ref(0);
const forceScroll = ref(false);
const focusTick = ref(0);

// ── derived ───────────────────────────────────────────────────────────────
const locked = computed(() => messages.value.length > 0);
const needsSetup = computed(() => loaded.value && (!agents.value.length || !models.value.length));
const uploading = computed(() => attachments.value.some((a) => a.status === "uploading"));
const paused = computed(() => {
	const last = messages.value[messages.value.length - 1];
	return Boolean(last?.questions?.length);
});

function agentLabel(name) {
	return agents.value.find((a) => a.name === name)?.title || name;
}
function modelLabel(name) {
	if (!name) return null;
	return models.value.find((m) => m.name === name)?.title || name;
}

// ── lifecycle / data loading ────────────────────────────────────────────────
async function loadInitial() {
	try {
		const [a, m] = await Promise.all([api.loadAgents(), api.loadModels(), refreshHistory()]);
		agents.value = a;
		models.value = m;
		const assistant = a.find((x) => x.name === "Flow");
		selectedAgent.value = assistant ? assistant.name : a[0]?.name ?? null;
		loadToolApproval(selectedAgent.value);
		loaded.value = true;
		focusTick.value++;

		if (readPanelState().open) await restoreSession();
	} catch {
		// `loaded` stays false, keeping the composer disabled on "Loading…".
		frappe.show_alert({
			message: __("Flow failed to load. Refresh the page to retry."),
			indicator: "red",
		});
	}
}

let sessionRestored = false;
async function restoreSession() {
	if (sessionRestored) return;
	sessionRestored = true;
	const { session } = readPanelState();
	if (!session) return;
	try {
		await switchSession(session);
	} catch {
		newChat();
	}
}

async function refreshHistory() {
	recentSessions.value = await api.loadHistory();
}

// Load the classification map for `agent`. The cache serves instantly and is
// refreshed in the background, so an edited Flow Tool doesn't stay stale all
// session. Guarded against a stale response winning after a quick agent switch.
function loadToolApproval(agent) {
	if (!agent) {
		toolApproval.value = {};
		return Promise.resolve();
	}
	const cached = toolApprovalCache[agent];
	if (cached) toolApproval.value = cached;
	const refresh = api
		.getAgentTools(agent)
		.then((map) => {
			toolApprovalCache[agent] = map;
			if (selectedAgent.value === agent) toolApproval.value = map;
		})
		.catch(() => {
			if (selectedAgent.value === agent && !cached) toolApproval.value = {};
		});
	return cached ? Promise.resolve() : refresh;
}

// ── selection ────────────────────────────────────────────────────────────────
function setAgent(name) {
	if (locked.value) return;
	selectedAgent.value = name;
	loadToolApproval(name);
}
function setModel(name) {
	selectedModel.value = name;
}

// ── conversation control ──────────────────────────────────────────────────────
function newChat() {
	if (sending.value) return;
	sessionName.value = null;
	runName.value = null;
	messages.value = [];
	attachments.value = [];
	focusTick.value++;
}

// ── attachments ────────────────────────────────────────────────────────────────
function attachFiles(fileList) {
	for (const f of Array.from(fileList || [])) {
		const length = attachments.value.push({
			uid: nextAttachmentId(),
			file: null,
			file_name: f.name,
			file_size: f.size,
			status: "uploading",
			error: "",
		});
		// Grab the reactive proxy (not the raw object) so the async mutations below
		// trigger updates; uploads run concurrently.
		uploadAndStage(f, attachments.value[length - 1]);
	}
}

async function uploadAndStage(f, item) {
	try {
		const uploaded = await api.uploadFile(f);
		const chip = await api.attachFile(uploaded.name);
		item.file = chip.file;
		item.file_name = chip.file_name;
		item.file_size = chip.file_size;
		item.status = "ready";
	} catch (e) {
		item.status = "error";
		item.error = e?.message || "";
	}
}

function removeAttachment(uid) {
	attachments.value = attachments.value.filter((a) => a.uid !== uid);
}

// Bumped per switch so a slow load can't write into a newer session's view.
let switchSeq = 0;

async function switchSession(name) {
	// A paused run is restored on return (restorePausedRun); only block mid-stream.
	if (sending.value) return;
	const seq = ++switchSeq;
	sessionName.value = name;
	runName.value = null;
	messages.value = [];
	attachments.value = [];

	// A prior stream cut off mid-flight may have left a Running run; clear it so the
	// reloaded session can start a new turn instead of being blocked.
	await api.recoverSession(name).catch(() => {});

	const doc = await api.getSession(name);
	if (seq !== switchSeq) return;
	selectedAgent.value = doc.agent;
	selectedModel.value = doc.model || null;
	await loadToolApproval(doc.agent);
	if (seq !== switchSeq) return;

	// Attachments are linked to their turn by run; group so each user message
	// can render its own chips.
	const attachmentsByRun = {};
	for (const a of doc.attachments || []) {
		(attachmentsByRun[a.run] ||= []).push({ file_name: a.file_name, file_size: a.file_size });
	}

	// Merge consecutive assistant rows (one per iteration in the doc) into one
	// message, as live does — otherwise the tool grouping fragments per iteration.
	let current = null;
	for (const m of doc.messages || []) {
		if (m.role === "user") {
			current = null;
			messages.value.push({
				id: nextId(),
				role: "user",
				content: m.content,
				attachments: attachmentsByRun[m.run] || [],
			});
		} else if (m.role === "assistant") {
			if (!current) current = pushAssistant(false);
			if (m.run) current.runName = m.run;
			if (m.content) current.parts.push(makeTextPart(m.content));
			for (const t of parseToolCalls(m.tool_calls)) {
				current.parts.push(makeToolPart(t.id, t.function.name, t.function.arguments));
			}
		} else if (m.role === "tool" && current) {
			setToolResult(current, m.tool_call_id, m.content);
		}
	}

	// A turn whose stream died before persisting a reply leaves a user message with
	// no assistant message after it; flag it so the UI notes the interruption rather
	// than showing a bare, unanswered bubble.
	const built = messages.value;
	for (let i = 0; i < built.length; i++) {
		if (built[i].role === "user" && built[i + 1]?.role !== "assistant")
			built[i].interrupted = true;
	}

	await restoreFeedback(name, seq);
	requestScroll();
	await restorePausedRun(name);
}

async function restoreFeedback(session, seq) {
	const runs = await api.getRunFeedback(session).catch(() => []);
	if (seq !== switchSeq || !runs.length) return;
	const byRun = new Map(runs.map((r) => [r.name, r]));
	for (const m of messages.value) {
		const fb = m.runName && byRun.get(m.runName);
		if (fb) m.feedback = { rating: fb.feedback_rating, comment: fb.feedback_comment || "" };
	}
}

async function restorePausedRun(session) {
	const runs = await api.getPausedRun(session);
	if (sessionName.value !== session || !runs.length || !runs[0].questions) return;
	const questions = JSON.parse(runs[0].questions);
	if (!questions.length) return;

	const last = [...messages.value].reverse().find((m) => m.role === "assistant");
	if (!last) return;
	last.questions = prepareQuestions(questions);
	last.runName = runs[0].name;
	runName.value = runs[0].name;
	requestScroll();
}

// ── sending / streaming ────────────────────────────────────────────────────────
// Aborts the in-flight stream when the user stops the response.
let abortController = null;

async function send(text) {
	text = text.trim();
	if (!text || sending.value || paused.value || uploading.value) return;

	const ready = attachments.value.filter((a) => a.status === "ready");
	const files = ready.map((a) => a.file);
	const chips = ready.map((a) => ({ file_name: a.file_name, file_size: a.file_size }));
	attachments.value = [];

	messages.value.push({ id: nextId(), role: "user", content: text, attachments: chips });
	const assistant = pushAssistant();
	sending.value = true;
	abortController = new AbortController();
	requestScroll(true);

	try {
		await startRun(
			{
				input: text,
				...(files.length && { attachments: files }),
				...(sessionName.value && { session: sessionName.value }),
				...(selectedAgent.value && !sessionName.value && { agent: selectedAgent.value }),
				...(selectedModel.value && { model: selectedModel.value }),
			},
			(event) => handleEvent(event, assistant),
			abortController.signal
		);
	} catch (e) {
		if (e.name === "AbortError") assistant.pending = false;
		else failMessage(assistant, e);
	} finally {
		abortController = null;
		sending.value = false;
		requestScroll();
		focusTick.value++;
	}
}

async function resume(answers, pausedMsg) {
	const rn = pausedMsg?.runName || runName.value;
	if (!rn) return;

	// Stream the resumed turn into the same message so the whole run stays one block
	// (matches how a reload reconstructs it) instead of splitting at each approval.
	pausedMsg.questions = [];
	pausedMsg.pending = true;
	sending.value = true;
	abortController = new AbortController();
	requestScroll(true);

	try {
		await resumeRun(
			{ run_name: rn, answers },
			(event) => handleEvent(event, pausedMsg),
			abortController.signal
		);
	} catch (e) {
		if (e.name === "AbortError") pausedMsg.pending = false;
		else failMessage(pausedMsg, e);
	} finally {
		abortController = null;
		sending.value = false;
		requestScroll();
		focusTick.value++;
	}
}

// Stop the response: abort the live stream and finalize its run so the session
// isn't left blocked. The backend agent loop unwinds on the aborted connection.
function stopRun() {
	if (!sending.value) return;
	abortController?.abort();
	const rn = runName.value;
	// Stopped before run_started arrived: no run name yet, so finalize any Running
	// run on the session instead so the next turn isn't briefly blocked.
	if (rn) api.stopRun(rn).catch(() => {});
	else if (sessionName.value) api.recoverSession(sessionName.value).catch(() => {});
}

// Record thumbs feedback on a finished turn (rating "None" clears it). A Down comment
// is saved as agent memory server-side. Local state updates only after the server accepts.
async function submitFeedback(msg, rating, comment = "") {
	const result = await api.submitFeedback({
		run_name: msg.runName,
		rating,
		comment: comment || null,
	});
	msg.feedback = rating === "None" ? null : { rating, comment };
	return result;
}

// Records one answer and stamps the tool's approval state; once every question
// on the paused message is answered, resumes the run with all answers at once.
// A Deny is sent through like any answer — the agent records it and stops the run.
function answerQuestion(msg, question, answer) {
	const a = (answer || "").trim();
	if (!a || !msg) return;

	question._answer = a;
	const tool = msg.parts.find((p) => p.type === "tool" && p.id === question.key);
	if (tool)
		tool.approval = a === "Approve" ? "approved" : a === "Deny" ? "denied" : "redirected";

	if (msg.questions.some((q) => q._answer === undefined)) return;

	const answers = {};
	msg.questions.forEach((q) => (answers[q.key] = q._answer));
	resume(answers, msg);
}

function handleEvent(event, msg) {
	switch (event.type) {
		case "run_started":
			runName.value = event.name;
			sessionName.value = event.session;
			msg.runName = event.name;
			break;
		case "text":
			appendText(msg, event.delta);
			requestScroll();
			break;
		case "tool_started": {
			// Fired twice: once mid-stream (no args yet), then again with the full arguments before
			// the tool runs. Create the card on the first, fill its arguments on the second.
			const part = msg.parts.find((p) => p.type === "tool" && p.id === event.id);
			if (part) part.arguments = event.arguments;
			else msg.parts.push(makeToolPart(event.id, event.name, event.arguments));
			requestScroll();
			break;
		}
		case "tool_ended":
			setToolResult(msg, event.id, event.result);
			requestScroll();
			break;
		case "done":
			msg.pending = false;
			if (event.status === "Paused") {
				msg.questions = prepareQuestions(event.questions);
				msg.runName = runName.value;
				requestScroll(true);
			}
			refreshHistory();
			break;
		case "error":
			appendText(msg, `\n\n${__("Error")}: ${event.message}`);
			msg.pending = false;
			break;
	}
}

// ── helpers ──────────────────────────────────────────────────────────────────
// Single source of the part shapes, shared by the live stream and the session
// reload so the two paths can't drift apart.
const makeTextPart = (text) => ({ id: nextId(), type: "text", text });
const makeToolPart = (id, name, args) => ({
	id,
	type: "tool",
	name: normalizeToolName(name),
	arguments: args,
	result: null,
	approval: null,
});

function setToolResult(msg, id, result) {
	const part = msg.parts.find((p) => p.type === "tool" && p.id === id);
	if (!part) return;
	part.result = result;
	// On reload the live approval state is gone; recover it from the persisted
	// confirmation result so the "Denied"/"Changes requested" badge survives. Gated on
	// the tool being a confirmation tool so a regular tool whose result happens to carry
	// a {status: "denied"} payload isn't mislabeled.
	if (part.approval === null && toolApproval.value[part.name] === true)
		part.approval = approvalFromResult(result);
}

// A denied/redirected confirmation persists a known status payload as its tool result.
function approvalFromResult(result) {
	if (typeof result !== "string") return null;
	try {
		const status = JSON.parse(result)?.status;
		if (status === "denied") return "denied";
		if (status === "redirect") return "redirected";
	} catch {
		// a normal tool result, not a confirmation payload
	}
	return null;
}

function pushAssistant(pending = true) {
	const msg = {
		id: nextId(),
		role: "assistant",
		parts: [],
		pending,
		questions: [],
		runName: null,
		feedback: null,
	};
	messages.value.push(msg);
	// Return the reactive proxy, not the raw object — streaming mutates this after
	// render, so it must go through the proxy to trigger updates.
	return messages.value[messages.value.length - 1];
}

function appendText(msg, delta) {
	const last = msg.parts[msg.parts.length - 1];
	// Only open a new text part on real text. A whitespace-only delta between tool calls
	// (some models emit these) would otherwise split one activity group into two.
	if (last && last.type === "text") last.text += delta;
	else if (delta.trim()) msg.parts.push(makeTextPart(delta));
}

function failMessage(msg, error) {
	appendText(msg, `\n\n${__("Error")}: ${error.message}`);
	msg.pending = false;
}

function parseToolCalls(raw) {
	if (!raw) return [];
	try {
		return JSON.parse(raw);
	} catch {
		return [];
	}
}

function prepareQuestions(questions) {
	return (questions || []).map((q) => ({
		...q,
		_showOther: false,
		_otherText: "",
		_answer: undefined,
	}));
}

// force bypasses the "stick" guard — for explicit actions (sending, approval
// cards) that must land at the bottom even if the user scrolled up.
function requestScroll(force = false) {
	if (force) forceScroll.value = true;
	scrollTick.value++;
}

export function useStore() {
	return {
		// state
		agents,
		models,
		recentSessions,
		selectedAgent,
		selectedModel,
		sessionName,
		messages,
		attachments,
		sending,
		loaded,
		fullscreen,
		toolApproval,
		scrollTick,
		forceScroll,
		focusTick,
		// derived
		locked,
		needsSetup,
		paused,
		uploading,
		agentLabel,
		modelLabel,
		// actions
		loadInitial,
		restoreSession,
		refreshHistory,
		setAgent,
		setModel,
		newChat,
		switchSession,
		send,
		stopRun,
		answerQuestion,
		submitFeedback,
		attachFiles,
		removeAttachment,
	};
}
