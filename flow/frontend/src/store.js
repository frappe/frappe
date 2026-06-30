import { ref, computed } from "vue";
import * as api from "@/api/client";
import { startRun, resumeRun } from "@/api/stream";

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
	const [a, m] = await Promise.all([api.loadAgents(), api.loadModels(), refreshHistory()]);
	agents.value = a;
	models.value = m;
	const assistant = a.find((x) => x.name === "Flow");
	selectedAgent.value = assistant ? assistant.name : a[0]?.name ?? null;
	loaded.value = true;
	focusTick.value++;
}

async function refreshHistory() {
	recentSessions.value = await api.loadHistory();
}

// ── selection ────────────────────────────────────────────────────────────────
function setAgent(name) {
	if (locked.value) return;
	selectedAgent.value = name;
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

async function switchSession(name) {
	// A paused run is restored on return (restorePausedRun); only block mid-stream.
	if (sending.value) return;
	sessionName.value = name;
	runName.value = null;
	messages.value = [];
	attachments.value = [];

	// A prior stream cut off mid-flight may have left a Running run; clear it so the
	// reloaded session can start a new turn instead of being blocked.
	await api.recoverSession(name).catch(() => {});

	const doc = await api.getSession(name);
	selectedAgent.value = doc.agent;
	selectedModel.value = doc.model || null;

	// Attachments are linked to their turn by run; group so each user message
	// can render its own chips.
	const attachmentsByRun = {};
	for (const a of doc.attachments || []) {
		(attachmentsByRun[a.run] ||= []).push({ file_name: a.file_name, file_size: a.file_size });
	}

	let current = null;
	for (const m of doc.messages || []) {
		if (m.role === "user") {
			messages.value.push({
				id: nextId(),
				role: "user",
				content: m.content,
				attachments: attachmentsByRun[m.run] || [],
			});
		} else if (m.role === "assistant") {
			const parts = [];
			if (m.content) parts.push({ id: nextId(), type: "text", text: m.content });
			for (const t of parseToolCalls(m.tool_calls)) {
				parts.push({
					id: t.id,
					type: "tool",
					name: t.function.name,
					arguments: t.function.arguments,
					result: null,
					expanded: false,
					approval: null,
				});
			}
			current = {
				id: nextId(),
				role: "assistant",
				parts,
				pending: false,
				questions: [],
				runName: null,
			};
			messages.value.push(current);
		} else if (m.role === "tool" && current) {
			const part = current.parts.find((p) => p.type === "tool" && p.id === m.tool_call_id);
			if (part) part.result = m.content;
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

	requestScroll();
	await restorePausedRun(name);
}

async function restorePausedRun(session) {
	const runs = await api.getPausedRun(session);
	if (!runs.length || !runs[0].questions) return;
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
			(event) => handleEvent(event, assistant)
		);
	} catch (e) {
		failMessage(assistant, e);
	} finally {
		sending.value = false;
		requestScroll();
		focusTick.value++;
	}
}

async function resume(answers, pausedMsg) {
	const rn = pausedMsg?.runName || runName.value;
	if (!rn) return;

	pausedMsg.questions = [];
	const assistant = pushAssistant();
	sending.value = true;
	requestScroll(true);

	try {
		await resumeRun({ run_name: rn, answers }, (event) => handleEvent(event, assistant));
	} catch (e) {
		failMessage(assistant, e);
	} finally {
		sending.value = false;
		requestScroll();
		focusTick.value++;
	}
}

// Records one answer and stamps the tool's approval state; once every question
// on the paused message is answered, resumes the run with all answers at once.
function answerQuestion(question, answer) {
	const a = (answer || "").trim();
	if (!a) return;

	const pausedMsg = messages.value[messages.value.length - 1];
	if (!pausedMsg) return;

	question._answer = a;
	const tool = pausedMsg.parts.find((p) => p.type === "tool" && p.id === question.key);
	if (tool)
		tool.approval = a === "Approve" ? "approved" : a === "Deny" ? "denied" : "redirected";

	if (pausedMsg.questions.some((q) => q._answer === undefined)) return;

	const answers = {};
	pausedMsg.questions.forEach((q) => (answers[q.key] = q._answer));
	resume(answers, pausedMsg);
}

function handleEvent(event, msg) {
	switch (event.type) {
		case "run_started":
			runName.value = event.name;
			sessionName.value = event.session;
			break;
		case "text":
			appendText(msg, event.delta);
			requestScroll();
			break;
		case "tool_started":
			msg.parts.push({
				id: event.id,
				type: "tool",
				name: event.name,
				arguments: event.arguments,
				result: null,
				expanded: false,
				approval: null,
			});
			requestScroll();
			break;
		case "tool_ended": {
			// A resumed confirmation tool's card lives in the earlier paused message,
			// not the new one being streamed into — so search all messages.
			const part = findToolPart(event.id);
			if (part) part.result = event.result;
			requestScroll();
			break;
		}
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
			appendText(msg, `\n\nError: ${event.message}`);
			msg.pending = false;
			break;
	}
}

// ── helpers ──────────────────────────────────────────────────────────────────
function pushAssistant() {
	const msg = {
		id: nextId(),
		role: "assistant",
		parts: [],
		pending: true,
		questions: [],
		runName: null,
	};
	messages.value.push(msg);
	// Return the reactive proxy, not the raw object — streaming mutates this after
	// render, so it must go through the proxy to trigger updates.
	return messages.value[messages.value.length - 1];
}

function appendText(msg, delta) {
	const last = msg.parts[msg.parts.length - 1];
	if (last && last.type === "text") last.text += delta;
	else msg.parts.push({ id: nextId(), type: "text", text: delta });
}

function findToolPart(id) {
	for (const m of messages.value) {
		const tc = (m.parts || []).find((p) => p.type === "tool" && p.id === id);
		if (tc) return tc;
	}
	return null;
}

function failMessage(msg, error) {
	appendText(msg, `\n\nError: ${error.message}`);
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
		refreshHistory,
		setAgent,
		setModel,
		newChat,
		switchSession,
		send,
		answerQuestion,
		attachFiles,
		removeAttachment,
	};
}
