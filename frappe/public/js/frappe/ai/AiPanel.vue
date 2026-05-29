<script setup>
import { ref, computed, nextTick, onMounted, h } from "vue";

const props = defineProps({
	onClose: Function,
});

// ── icons (inline svg, matches design) ──────────────────────────────────────
const ICONS = {
	sparkle: '<path d="M12 3l1.7 4.6L18 9l-4.3 1.4L12 15l-1.7-4.6L6 9l4.3-1.4L12 3z"/><path d="M19 14l.8 2.2L22 17l-2.2.8L19 20l-.8-2.2L16 17l2.2-.8L19 14z"/>',
	history: '<circle cx="12" cy="12" r="9"/><polyline points="12 7 12 12 15.5 14"/>',
	plus: '<line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/>',
	x: '<line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>',
	"chevron-down": '<polyline points="6 9 12 15 18 9"/>',
	"chevron-right": '<polyline points="9 6 15 12 9 18"/>',
	send: '<path d="M22 2L11 13"/><path d="M22 2l-7 20-4-9-9-4 20-7z"/>',
	shield: '<path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"/>',
	check: '<polyline points="20 6 9 17 4 12"/>',
};
const Icon = (p) =>
	h("svg", {
		width: p.size || 16,
		height: p.size || 16,
		viewBox: "0 0 24 24",
		fill: "none",
		stroke: "currentColor",
		"stroke-width": p.strokeWidth || 1.5,
		"stroke-linecap": "round",
		"stroke-linejoin": "round",
		innerHTML: ICONS[p.name] || "",
	});
Icon.props = ["name", "size", "strokeWidth"];

// ── state ──────────────────────────────────────────────────────────────────
const agents = ref([]);
const models = ref([]);
const recentSessions = ref([]);
const selectedAgent = ref(null);
const selectedModel = ref(null);
const sessionName = ref(null);
const messages = ref([]); // { role, content, tool_calls, pending, questions, runName }
const inputText = ref("");
const sending = ref(false);
const messagesEl = ref(null);
const textareaEl = ref(null);
const runName = ref(null);

const agentOpen = ref(false);
const modelOpen = ref(false);
const sessionsOpen = ref(false);

const loaded = ref(false);

const paused = computed(() => {
	const last = messages.value[messages.value.length - 1];
	return last?.questions?.length > 0;
});
// agent is locked once a conversation has started (you can't switch an agent mid-session)
const locked = computed(() => messages.value.length > 0);
// no usable agent/model configured yet — show setup guidance
const needsSetup = computed(() => loaded.value && (!agents.value.length || !models.value.length));

// ── lifecycle ──────────────────────────────────────────────────────────────
onMounted(async () => {
	await Promise.all([loadAgents(), loadModels(), loadHistory()]);
	loaded.value = true;
	nextTick(() => textareaEl.value?.focus());
});

// ── data loading ──────────────────────────────────────────────────────────
async function loadAgents() {
	const r = await frappe.xcall("frappe.client.get_list", {
		doctype: "AI Agent",
		filters: { enabled: 1 },
		fields: ["name", "title"],
		limit: 50,
	});
	agents.value = r;
	const assistant = r.find((a) => a.name === "Assistant");
	selectedAgent.value = assistant ? assistant.name : r[0]?.name ?? null;
}

async function loadModels() {
	const r = await frappe.xcall("frappe.client.get_list", {
		doctype: "AI Model",
		filters: { enabled: 1 },
		fields: ["name", "title"],
		limit: 50,
	});
	models.value = r;
}

async function loadHistory() {
	if (!window.frappe) return;
	const r = await frappe.xcall("frappe.client.get_list", {
		doctype: "AI Session",
		filters: { owner: frappe.session.user },
		fields: ["name", "title", "creation"],
		order_by: "creation desc",
		limit: 15,
	});
	recentSessions.value = r;
}

async function switchSession(name) {
	if (sending.value || paused.value) return;
	sessionsOpen.value = false;
	sessionName.value = name;
	runName.value = null;
	messages.value = [];

	try {
		const doc = await frappe.xcall("frappe.client.get", { doctype: "AI Session", name: name });
		selectedAgent.value = doc.agent;
		selectedModel.value = doc.model || null;
		let currentAssistantMsg = null;

		for (const m of doc.messages || []) {
			if (m.role === "user") {
				messages.value.push({ role: "user", content: m.content });
			} else if (m.role === "assistant") {
				const parts = [];
				if (m.content) parts.push({ type: "text", text: m.content });
				if (m.tool_calls) {
					try {
						JSON.parse(m.tool_calls).forEach((t) =>
							parts.push({
								type: "tool",
								id: t.id,
								name: t.function.name,
								arguments: t.function.arguments,
								result: null,
								expanded: false,
							})
						);
					} catch (e) {}
				}
				currentAssistantMsg = { role: "assistant", parts, pending: false, questions: [] };
				messages.value.push(currentAssistantMsg);
			} else if (m.role === "tool") {
				if (currentAssistantMsg) {
					const tc = currentAssistantMsg.parts.find((p) => p.type === "tool" && p.id === m.tool_call_id);
					if (tc) tc.result = m.content;
				}
			}
		}
		scrollToBottom();
	} catch (e) {
		frappe.msgprint("Failed to load session");
	}
}

// ── send message ──────────────────────────────────────────────────────────
async function send() {
	const text = inputText.value.trim();
	if (!text || sending.value || paused.value) return;

	inputText.value = "";
	sending.value = true;
	if (textareaEl.value) textareaEl.value.style.height = "auto";

	messages.value.push({ role: "user", content: text });
	messages.value.push({ role: "assistant", parts: [], pending: true, questions: [] });
	const assistantMsg = messages.value[messages.value.length - 1]; // reactive proxy
	scrollToBottom();

	try {
		const resp = await fetch(`/api/method/frappe.ai.api.start_run`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": frappe.csrf_token,
			},
			body: JSON.stringify({
				input: text,
				stream: true,
				...(sessionName.value && { session: sessionName.value }),
				...(selectedAgent.value && !sessionName.value && { agent: selectedAgent.value }),
				...(selectedModel.value && { model: selectedModel.value }),
			}),
		});

		await consumeStream(resp, assistantMsg);
	} catch (e) {
		assistantMsg.content = `Error: ${e.message}`;
		assistantMsg.pending = false;
	} finally {
		sending.value = false;
		scrollToBottom();
	}
}

async function consumeStream(resp, assistantMsg) {
	const reader = resp.body.getReader();
	const decoder = new TextDecoder();
	let buffer = "";

	while (true) {
		const { done, value } = await reader.read();
		if (done) break;
		buffer += decoder.decode(value, { stream: true });

		const blocks = buffer.split("\n\n");
		buffer = blocks.pop();

		for (const block of blocks) {
			const dataLine = block.split("\n").find((l) => l.startsWith("data: "));
			if (!dataLine) continue;
			const event = JSON.parse(dataLine.slice(6));
			handleEvent(event, assistantMsg);
		}
	}
}

function appendText(msg, delta) {
	const last = msg.parts[msg.parts.length - 1];
	if (last && last.type === "text") last.text += delta;
	else msg.parts.push({ type: "text", text: delta });
}

function handleEvent(event, assistantMsg) {
	switch (event.type) {
		case "run_started":
			runName.value = event.name;
			sessionName.value = event.session;
			break;
		case "text":
			appendText(assistantMsg, event.delta);
			assistantMsg.pending = true;
			scrollToBottom();
			break;
		case "tool_started":
			assistantMsg.parts.push({
				type: "tool",
				id: event.id,
				name: event.name,
				arguments: event.arguments,
				result: null,
				expanded: false,
			});
			scrollToBottom();
			break;
		case "tool_ended":
			const tc = assistantMsg.parts.find((p) => p.type === "tool" && p.id === event.id);
			if (tc) tc.result = event.result;
			break;
		case "done":
			assistantMsg.pending = false;
			if (event.status === "Paused") {
				assistantMsg.questions = event.questions || [];
				assistantMsg.runName = runName.value;
			}
			loadHistory(); // refresh recent sessions
			break;
		case "error":
			appendText(assistantMsg, `\n\nError: ${event.message}`);
			assistantMsg.pending = false;
			break;
	}
}

async function resume(answers) {
	const last = messages.value[messages.value.length - 1];
	if (!last?.runName) return;

	sending.value = true;
	last.questions = [];
	messages.value.push({ role: "assistant", parts: [], pending: true, questions: [] });
	const assistantMsg = messages.value[messages.value.length - 1]; // reactive proxy
	scrollToBottom();

	try {
		const resp = await fetch(`/api/method/frappe.ai.api.resume_run`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json",
				"X-Frappe-CSRF-Token": frappe.csrf_token,
			},
			body: JSON.stringify({
				run_name: last.runName,
				answers: answers,
				stream: true,
			}),
		});
		await consumeStream(resp, assistantMsg);
	} catch (e) {
		assistantMsg.content = `Error: ${e.message}`;
		assistantMsg.pending = false;
	} finally {
		sending.value = false;
		scrollToBottom();
	}
}

function answerQuestion(question, answer) {
	const answers = {};
	answers[question.key] = answer;
	resume(answers);
}

function newChat() {
	sessionName.value = null;
	runName.value = null;
	messages.value = [];
	inputText.value = "";
	if (textareaEl.value) textareaEl.value.style.height = "auto";
	nextTick(() => textareaEl.value?.focus());
}

function pickAgent(a) {
	agentOpen.value = false;
	if (locked.value || a.name === selectedAgent.value) return;
	selectedAgent.value = a.name;
}

function pickModel(name) {
	modelOpen.value = false;
	selectedModel.value = name;
}

function scrollToBottom() {
	nextTick(() => {
		if (messagesEl.value) {
			messagesEl.value.scrollTop = messagesEl.value.scrollHeight;
		}
	});
}

function onKeydown(e) {
	if (e.key === "Enter" && !e.shiftKey) {
		e.preventDefault();
		send();
	}
}

function agentLabel(name) {
	return agents.value.find((a) => a.name === name)?.title || name;
}

function modelLabel(name) {
	if (!name) return __("Default");
	return models.value.find((m) => m.name === name)?.title || name;
}

function renderMarkdown(txt) {
	if (!txt) return "";
	let html = window.frappe ? frappe.markdown(txt) : txt;
	// wrap tables so a wide one scrolls on its own instead of widening the sidebar
	return html
		.replace(/<table(\s[^>]*)?>/g, '<div class="md-table-scroll"><table$1>')
		.replace(/<\/table>/g, "</table></div>");
}

function fmtArgs(args) {
	if (!args) return "";
	try {
		const obj = typeof args === "string" ? JSON.parse(args) : args;
		return JSON.stringify(obj, null, 2);
	} catch (_) {
		return String(args);
	}
}

function timeAgo(ds) {
	if (!ds) return "";
	return window.moment ? moment(ds).fromNow() : ds;
}
</script>

<template>
	<div class="chat-sidebar">
		<!-- Header -->
		<div class="cs-header">
			<div class="cs-header-row">
				<span class="brand-dot"><Icon name="sparkle" :size="11" :strokeWidth="2" /></span>
				<span class="cs-title">{{ __("AI Assistant") }}</span>
				<span class="spacer" />

				<div class="dd-root">
					<button class="fui-btn ghost sm icon" :title="__('Previous sessions')" @click="sessionsOpen = !sessionsOpen">
						<Icon name="history" :size="14" :strokeWidth="1.75" />
					</button>
					<template v-if="sessionsOpen">
						<div class="dd-overlay" @click="sessionsOpen = false" />
						<div class="sessions-menu right">
							<div class="sessions-head">
								<span class="sessions-head-title">{{ __("Recent sessions") }}</span>
								<button class="sessions-close" :title="__('Close')" @click="sessionsOpen = false"><Icon name="x" :size="14" :strokeWidth="2" /></button>
							</div>
							<div class="sessions-list thin-scroll">
								<button v-for="s in recentSessions" :key="s.name" class="session-item" @click="switchSession(s.name)">
									<span class="session-title">{{ s.title || s.name }}</span>
									<span class="session-meta">{{ timeAgo(s.creation) }}</span>
								</button>
								<div v-if="!recentSessions.length" class="sessions-empty">{{ __("No recent sessions") }}</div>
							</div>
						</div>
					</template>
				</div>

				<button class="fui-btn ghost sm icon" :title="__('New chat')" @click="newChat"><Icon name="plus" :size="14" :strokeWidth="2" /></button>
				<button class="fui-btn ghost sm icon" :title="__('Close (Ctrl+M)')" @click="onClose"><Icon name="x" :size="14" :strokeWidth="2" /></button>
			</div>
		</div>

		<!-- Messages -->
		<div class="messages thin-scroll" ref="messagesEl">
			<!-- setup guidance: no enabled agent/model -->
			<div v-if="needsSetup" class="cs-setup">
				<span class="brand-dot lg"><Icon name="sparkle" :size="18" :strokeWidth="2" /></span>
				<div class="empty-title">{{ __("Finish setup to start") }}</div>
				<div class="empty-sub">{{ __("The assistant needs a few things configured first:") }}</div>
				<ul class="setup-steps">
					<li v-if="!models.length">{{ __("Create and enable an AI Model with your provider credentials.") }}</li>
					<li v-if="!agents.length">{{ __("Enable an AI Agent (an Assistant is created automatically once a model exists).") }}</li>
					<li>{{ __("Enable Server Scripts in your site config so the assistant can run code.") }}</li>
				</ul>
			</div>

			<div v-else-if="messages.length === 0" class="cs-empty">
				<span class="brand-dot lg"><Icon name="sparkle" :size="18" :strokeWidth="2" /></span>
				<div class="empty-title">{{ __("AI Assistant") }}</div>
				<div class="empty-sub">{{ __("Ask about your data, draft records, or run a task.") }}</div>
			</div>

			<template v-for="(msg, i) in messages" :key="i">
				<!-- user -->
				<div v-if="msg.role === 'user'" class="msg user">
					<div class="msg-bubble user">{{ msg.content }}</div>
				</div>

				<!-- assistant -->
				<div v-else class="assistant-block">
					<div class="msg assistant">
						<div class="msg-body">
							<!-- text and tool calls, in arrival order -->
							<template v-for="(part, pi) in msg.parts" :key="pi">
								<div v-if="part.type === 'text' && part.text" class="ai-markdown" v-html="renderMarkdown(part.text)" />
								<div v-else-if="part.type === 'tool'" class="toolcall" :class="{ open: part.expanded }">
									<button class="toolcall-head" @click="part.expanded = !part.expanded">
										<Icon name="chevron-right" :size="13" :strokeWidth="2" class="tc-chevron" :class="{ open: part.expanded }" />
										<span class="tc-name">{{ part.name }}</span>
										<span class="tc-spacer" />
										<span class="tc-status">
											<span class="dot" :class="part.result === null ? 'running' : 'done'" />
											{{ part.result === null ? __("Running") : __("Done") }}
										</span>
									</button>
									<div v-if="part.expanded" class="toolcall-body">
										<div class="tc-section">
											<div class="tc-label">{{ __("Input") }}</div>
											<pre class="tc-code">{{ fmtArgs(part.arguments) }}</pre>
										</div>
										<div v-if="part.result !== null" class="tc-section">
											<div class="tc-label">{{ __("Output") }}</div>
											<pre class="tc-code">{{ part.result }}</pre>
										</div>
									</div>
								</div>
							</template>

							<!-- typing indicator before anything has streamed -->
							<div v-if="msg.pending && !msg.parts.length" class="ai-typing">
								<span /><span /><span />
							</div>

							<!-- confirmation -->
							<div v-if="msg.questions && msg.questions.length" class="confirms">
								<div v-for="q in msg.questions" :key="q.key" class="confirm">
									<div class="confirm-head">
										<span class="confirm-icon"><Icon name="shield" :size="14" :strokeWidth="1.75" /></span>
										<div class="confirm-prompt">
											<div class="confirm-title">{{ q.prompt }}</div>
										</div>
									</div>
									<div class="confirm-actions">
										<button
											v-for="opt in q.options"
											:key="opt"
											class="fui-btn sm"
											:class="opt === 'Approve' ? 'confirm-approve' : 'ghost'"
											@click="answerQuestion(q, opt)"
										>
											{{ opt === "Approve" ? __("Approve & run") : opt }}
										</button>
									</div>
									<div v-if="q.allow_other !== false" class="confirm-other">
										<input
											type="text"
											:placeholder="__('Or type a response…')"
											@keydown.enter.prevent="answerQuestion(q, $event.target.value)"
										/>
									</div>
								</div>
							</div>
						</div>
					</div>
				</div>
			</template>
		</div>

		<!-- Composer -->
		<div class="composer-wrap">
			<div class="composer">
				<textarea
					ref="textareaEl"
					v-model="inputText"
					:placeholder="needsSetup ? __('Setup required…') : __('Ask {0}…', [agentLabel(selectedAgent)])"
					:disabled="sending || paused || needsSetup"
					rows="1"
					@keydown="onKeydown"
					@input="$event.target.style.height = 'auto'; $event.target.style.height = Math.min($event.target.scrollHeight, 160) + 'px'"
				/>
				<div class="composer-controls">
					<!-- agent -->
					<div class="dd-root">
						<button class="ctl-trigger" :class="{ disabled: locked }" :title="__('Agent')" @click="!locked && (agentOpen = !agentOpen)">
							<span class="agent-dot" />
							<span class="ctl-value">{{ agentLabel(selectedAgent) }}</span>
							<Icon v-if="!locked" name="chevron-down" :size="11" :strokeWidth="2" />
						</button>
						<template v-if="agentOpen">
							<div class="dd-overlay" @click="agentOpen = false" />
							<div class="dd-menu up">
								<button
									v-for="a in agents"
									:key="a.name"
									class="dd-item"
									:class="{ selected: a.name === selectedAgent }"
									@click="pickAgent(a)"
								>
									<span class="item-title">{{ a.title }}</span>
								</button>
							</div>
						</template>
					</div>

					<span class="ctl-sep">/</span>

					<!-- model -->
					<div class="dd-root">
						<button class="ctl-trigger" :title="__('Model')" @click="modelOpen = !modelOpen">
							<span class="ctl-value">{{ modelLabel(selectedModel) }}</span>
							<Icon name="chevron-down" :size="11" :strokeWidth="2" />
						</button>
						<template v-if="modelOpen">
							<div class="dd-overlay" @click="modelOpen = false" />
							<div class="dd-menu up">
								<button class="dd-item" :class="{ selected: selectedModel === null }" @click="pickModel(null)">
									<span class="item-title">{{ __("Default") }}</span>
								</button>
								<button
									v-for="m in models"
									:key="m.name"
									class="dd-item"
									:class="{ selected: m.name === selectedModel }"
									@click="pickModel(m.name)"
								>
									<span class="item-title">{{ m.title }}</span>
								</button>
							</div>
						</template>
					</div>

					<span class="spacer" />
					<button class="send-btn" :disabled="!inputText.trim() || sending || paused || needsSetup" :title="__('Send')" @click="send">
						<Icon name="send" :size="12" :strokeWidth="2" />
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<style scoped>
.chat-sidebar {
	display: flex;
	flex-direction: column;
	height: 100%;
	background: var(--surface-white);
	border-left: 1px solid var(--outline-gray-2);
	font-size: var(--text-sm);
	color: var(--ink-gray-9);
}

/* Header */
.cs-header {
	flex: 0 0 auto;
	border-bottom: 1px solid var(--outline-gray-1);
	background: var(--surface-white);
}
.cs-header-row {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 8px 10px 8px 12px;
}
.cs-title {
	font-size: var(--text-sm);
	font-weight: var(--weight-semibold);
	letter-spacing: 0.01em;
	color: var(--ink-gray-9);
}
.cs-header-row .spacer {
	flex: 1;
}
.brand-dot {
	width: 18px;
	height: 18px;
	background: linear-gradient(135deg, var(--gray-900), var(--gray-700));
	color: #fff;
	border-radius: 5px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	flex: 0 0 auto;
}
.brand-dot.lg {
	width: 30px;
	height: 30px;
	border-radius: 8px;
}

/* fui buttons */
.fui-btn {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	height: 28px;
	padding: 0 10px;
	font-family: inherit;
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
	color: var(--ink-gray-9);
	background: var(--gray-100);
	border: 1px solid transparent;
	border-radius: var(--border-radius-sm);
	cursor: pointer;
	user-select: none;
}
.fui-btn:hover {
	background: var(--gray-200);
}
.fui-btn.ghost {
	background: transparent;
}
.fui-btn.ghost:hover {
	background: var(--gray-100);
}
.fui-btn.icon {
	width: 28px;
	padding: 0;
	justify-content: center;
}
.fui-btn.sm {
	height: 24px;
	font-size: var(--text-xs);
	padding: 0 8px;
	border-radius: 6px;
}
.fui-btn.sm.icon {
	width: 24px;
	padding: 0;
}

/* Messages */
.messages {
	flex: 1 1 auto;
	min-height: 0;
	overflow-y: auto;
	padding: 20px 16px 16px 16px;
	display: flex;
	flex-direction: column;
	gap: 22px;
}
.cs-empty {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	text-align: center;
	gap: 10px;
	color: var(--ink-gray-6);
}
.empty-title {
	font-size: var(--text-lg);
	font-weight: var(--weight-semibold);
	color: var(--ink-gray-9);
}
.empty-sub {
	font-size: var(--text-xs);
	color: var(--ink-gray-6);
	line-height: 1.5;
	max-width: 240px;
}

.cs-setup {
	flex: 1;
	display: flex;
	flex-direction: column;
	align-items: center;
	justify-content: center;
	text-align: center;
	gap: 10px;
	color: var(--ink-gray-6);
}
.setup-steps {
	margin: 4px 0 0;
	padding: 0;
	list-style: none;
	display: flex;
	flex-direction: column;
	gap: 8px;
	max-width: 280px;
	text-align: left;
}
.setup-steps li {
	position: relative;
	padding: 8px 10px 8px 28px;
	font-size: var(--text-xs);
	line-height: 1.5;
	color: var(--ink-gray-8);
	background: var(--surface-gray-1);
	border: 1px solid var(--outline-gray-1);
	border-radius: 8px;
	counter-increment: setup;
}
.setup-steps {
	counter-reset: setup;
}
.setup-steps li::before {
	content: counter(setup);
	position: absolute;
	left: 8px;
	top: 8px;
	width: 14px;
	height: 14px;
	border-radius: 999px;
	background: var(--gray-900);
	color: #fff;
	font-size: 9px;
	font-weight: var(--weight-semibold);
	display: inline-flex;
	align-items: center;
	justify-content: center;
}

.msg.user {
	display: flex;
	justify-content: flex-end;
}
.msg-bubble.user {
	background: var(--surface-gray-2);
	color: var(--ink-gray-9);
	padding: 10px 14px;
	border-radius: 14px 14px 4px 14px;
	font-size: var(--text-base);
	line-height: 1.6;
	max-width: 88%;
	white-space: pre-wrap;
}

.assistant-block {
	display: flex;
	flex-direction: column;
	gap: 10px;
}
.msg.assistant {
	display: block;
}
.msg.assistant .msg-body {
	font-size: var(--text-base);
	line-height: 1.7;
	color: var(--ink-gray-8);
	display: flex;
	flex-direction: column;
	gap: 10px;
	min-width: 0;
}
.msg.assistant .msg-body > * {
	min-width: 0;
	max-width: 100%;
}

/* Tool calls */
.toolcall {
	background: var(--surface-white);
	border: 1px solid var(--outline-gray-2);
	border-radius: var(--border-radius-sm);
	overflow: hidden;
}
.toolcall-head {
	width: 100%;
	display: flex;
	align-items: center;
	gap: 7px;
	padding: 8px 11px;
	background: transparent;
	border: 0;
	cursor: pointer;
	text-align: left;
	font-size: var(--text-sm);
	font-family: inherit;
	color: var(--ink-gray-8);
}
.toolcall-head:hover {
	background: var(--surface-gray-2);
}
.tc-chevron {
	color: var(--ink-gray-5);
	transition: transform 0.15s;
}
.tc-chevron.open {
	transform: rotate(90deg);
}
.tc-name {
	font-size: var(--text-sm);
	color: var(--ink-gray-8);
	font-weight: var(--weight-regular);
}
.tc-spacer {
	flex: 1;
}
.tc-status {
	display: inline-flex;
	align-items: center;
	gap: 6px;
	flex: 0 0 auto;
	font-size: var(--text-xs);
	color: var(--ink-gray-5);
	font-weight: var(--weight-regular);
}
.dot {
	width: 6px;
	height: 6px;
	border-radius: 999px;
	background: var(--ink-gray-4);
}
.dot.done {
	background: var(--green-500);
}
.dot.running {
	background: var(--ink-gray-4);
	animation: ai-pulse 1s ease-in-out infinite;
}
@keyframes ai-pulse {
	0%, 100% { opacity: 0.3; }
	50% { opacity: 1; }
}
.toolcall-body {
	padding: 4px 10px 12px;
	border-top: 1px solid var(--outline-gray-1);
	display: flex;
	flex-direction: column;
	gap: 10px;
}
.tc-label {
	font-size: 10.5px;
	letter-spacing: 0.06em;
	text-transform: uppercase;
	color: var(--ink-gray-5);
	font-weight: var(--weight-semibold);
	margin: 10px 0 5px;
}
.tc-code {
	font-family: var(--font-stack-monospace, ui-monospace, monospace);
	font-size: 11.5px;
	line-height: 1.55;
	margin: 0;
	padding: 8px 10px;
	background: var(--surface-gray-1);
	border: 1px solid var(--outline-gray-1);
	border-radius: 6px;
	color: var(--ink-gray-8);
	white-space: pre-wrap;
	word-break: break-word;
	overflow-x: auto;
}

/* Confirmation card */
.confirms {
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.confirm {
	background: var(--surface-gray-1);
	border: 1px solid var(--outline-gray-2);
	border-radius: var(--border-radius-sm);
	padding: 10px;
	display: flex;
	flex-direction: column;
	gap: 8px;
}
.confirm-head {
	display: flex;
	align-items: flex-start;
	gap: 8px;
}
.confirm-icon {
	width: 22px;
	height: 22px;
	border-radius: 6px;
	background: var(--surface-gray-3);
	color: var(--ink-gray-6);
	display: inline-flex;
	align-items: center;
	justify-content: center;
	flex: 0 0 auto;
}
.confirm-title {
	font-size: var(--text-sm);
	font-weight: var(--weight-medium);
	color: var(--ink-gray-9);
	line-height: 1.5;
	white-space: pre-wrap;
	word-break: break-word;
}
.confirm-actions {
	display: flex;
	gap: 6px;
	justify-content: flex-end;
}
.confirm-approve {
	background: var(--surface-white);
	color: var(--ink-gray-9);
	border: 1px solid var(--outline-gray-3);
	box-shadow: var(--shadow-xs);
}
.confirm-approve:hover {
	background: var(--surface-gray-1);
}
.confirm-other input {
	width: 100%;
	height: 28px;
	font-family: inherit;
	font-size: var(--text-xs);
	color: var(--ink-gray-9);
	background: var(--surface-white);
	border: 1px solid var(--outline-gray-2);
	border-radius: 6px;
	padding: 0 8px;
	outline: none;
}
.confirm-other input:focus {
	border-color: var(--gray-400);
	box-shadow: 0 0 0 2px var(--outline-gray-2);
}

/* Markdown */
.ai-markdown :deep(p) {
	margin: 0 0 8px;
}
.ai-markdown :deep(p:last-child) {
	margin-bottom: 0;
}
.ai-markdown :deep(h1),
.ai-markdown :deep(h2),
.ai-markdown :deep(h3),
.ai-markdown :deep(h4),
.ai-markdown :deep(h5),
.ai-markdown :deep(h6) {
	margin: 14px 0 6px;
	font-weight: var(--weight-semibold);
	line-height: 1.35;
	color: var(--ink-gray-9);
}
.ai-markdown :deep(h1):first-child,
.ai-markdown :deep(h2):first-child,
.ai-markdown :deep(h3):first-child {
	margin-top: 0;
}
.ai-markdown :deep(h1) {
	font-size: var(--text-lg);
}
.ai-markdown :deep(h2) {
	font-size: 15px;
}
.ai-markdown :deep(h3) {
	font-size: var(--text-base);
}
.ai-markdown :deep(h4),
.ai-markdown :deep(h5),
.ai-markdown :deep(h6) {
	font-size: var(--text-sm);
	color: var(--ink-gray-7);
}
.ai-markdown :deep(ul),
.ai-markdown :deep(ol) {
	margin: 4px 0;
	padding-left: 20px;
}
.ai-markdown :deep(li) {
	margin: 2px 0;
}
.ai-markdown :deep(a) {
	color: var(--blue-600);
	text-decoration: none;
}
.ai-markdown :deep(a):hover {
	text-decoration: underline;
}
.ai-markdown :deep(blockquote) {
	margin: 8px 0;
	padding: 2px 12px;
	border-left: 3px solid var(--outline-gray-2);
	color: var(--ink-gray-7);
}
.ai-markdown :deep(hr) {
	border: 0;
	border-top: 1px solid var(--outline-gray-1);
	margin: 12px 0;
}
.ai-markdown :deep(.md-table-scroll) {
	max-width: 100%;
	overflow-x: auto;
	margin: 8px 0;
	border: 1px solid var(--outline-gray-2);
	border-radius: 6px;
}
.ai-markdown :deep(table) {
	min-width: 100%;
	border-collapse: collapse;
	font-size: var(--text-xs);
}
.ai-markdown :deep(th),
.ai-markdown :deep(td) {
	padding: 6px 8px;
	border: 1px solid var(--outline-gray-1);
	text-align: left;
	vertical-align: top;
	line-height: 1.45;
}
.ai-markdown :deep(th) {
	background: var(--surface-gray-1);
	font-weight: var(--weight-semibold);
	color: var(--ink-gray-7);
}
.ai-markdown :deep(td) {
	color: var(--ink-gray-8);
}
.ai-markdown :deep(tr:nth-child(even) td) {
	background: var(--surface-gray-1);
}
.ai-markdown :deep(pre) {
	background: var(--surface-gray-1);
	border: 1px solid var(--outline-gray-1);
	border-radius: 6px;
	padding: 8px 10px;
	font-size: 11.5px;
	overflow-x: auto;
	margin: 8px 0;
}
.ai-markdown :deep(code) {
	font-family: var(--font-stack-monospace, ui-monospace, monospace);
	font-size: 11.5px;
}
.ai-markdown :deep(strong) {
	font-weight: var(--weight-medium);
	color: var(--ink-gray-9);
}

/* Typing */
.ai-typing {
	display: inline-flex;
	align-items: center;
	min-height: 20px;
	gap: 4px;
	color: var(--ink-gray-4);
}
.ai-typing span {
	width: 5px;
	height: 5px;
	background: currentColor;
	border-radius: 50%;
	animation: ai-bounce 1.4s infinite ease-in-out both;
}
.ai-typing span:nth-child(1) {
	animation-delay: -0.32s;
}
.ai-typing span:nth-child(2) {
	animation-delay: -0.16s;
}
@keyframes ai-bounce {
	0%, 80%, 100% { transform: scale(0); }
	40% { transform: scale(1); }
}

/* Composer */
.composer-wrap {
	flex: 0 0 auto;
	padding: 10px 12px 12px;
	border-top: 1px solid var(--outline-gray-1);
	background: var(--surface-white);
}
.composer {
	background: var(--surface-white);
	border: 1px solid var(--outline-gray-2);
	border-radius: var(--border-radius-md);
	box-shadow: var(--shadow-xs);
	padding: 8px 8px 6px 10px;
	display: flex;
	flex-direction: column;
	gap: 6px;
}
.composer:focus-within {
	border-color: var(--gray-400);
	box-shadow: 0 0 0 2px var(--outline-gray-2);
}
.composer textarea {
	width: 100%;
	resize: none;
	border: 0;
	outline: 0;
	font-family: inherit;
	font-size: var(--text-base);
	color: var(--ink-gray-9);
	background: transparent;
	min-height: 22px;
	max-height: 160px;
	line-height: 1.45;
}
.composer textarea::placeholder {
	color: var(--ink-gray-4);
}
.composer-controls {
	display: flex;
	align-items: center;
	gap: 6px;
	padding: 4px 2px 0;
}
.ctl-trigger {
	display: inline-flex;
	align-items: center;
	gap: 4px;
	height: 22px;
	padding: 0 6px;
	background: transparent;
	color: var(--ink-gray-6);
	border: 0;
	border-radius: 5px;
	cursor: pointer;
	font-family: inherit;
	font-size: 11.5px;
}
.ctl-trigger:hover {
	background: var(--surface-gray-2);
}
.ctl-trigger.disabled {
	cursor: default;
}
.ctl-trigger.disabled:hover {
	background: transparent;
}
.ctl-trigger .ctl-value {
	color: var(--ink-gray-8);
	font-weight: var(--weight-medium);
	white-space: nowrap;
}
.agent-dot {
	width: 6px;
	height: 6px;
	background: var(--green-500);
	border-radius: 999px;
	display: inline-block;
}
.ctl-sep {
	color: var(--ink-gray-3);
	padding: 0 2px;
}
.composer-controls .spacer {
	flex: 1;
}
.send-btn {
	width: 28px;
	height: 28px;
	border-radius: 7px;
	border: 0;
	cursor: pointer;
	background: var(--gray-900);
	color: #fff;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	flex: 0 0 auto;
}
.send-btn :deep(svg) {
	transform: translate(-1px, 1px);
}
.send-btn:hover:not(:disabled) {
	background: #000;
}
.send-btn:disabled {
	opacity: 0.4;
	cursor: not-allowed;
}

/* Dropdowns */
.dd-root {
	position: relative;
}
.dd-overlay {
	position: fixed;
	inset: 0;
	z-index: 30;
}
.dd-menu {
	position: absolute;
	top: calc(100% + 6px);
	left: 0;
	z-index: 31;
	width: 220px;
	background: var(--surface-white);
	border: 1px solid var(--outline-gray-2);
	border-radius: var(--border-radius-sm);
	box-shadow: var(--shadow-lg);
	padding: 4px;
	max-height: 320px;
	overflow-y: auto;
}
.dd-menu.up {
	top: auto;
	bottom: calc(100% + 6px);
}
.dd-item {
	display: block;
	width: 100%;
	background: transparent;
	border: 0;
	text-align: left;
	cursor: pointer;
	padding: 7px 8px;
	border-radius: 5px;
	color: var(--ink-gray-9);
	font-family: inherit;
	font-size: var(--text-xs);
}
.dd-item:hover {
	background: var(--surface-gray-2);
}
.dd-item.selected {
	background: var(--surface-gray-2);
}
.dd-item .item-title {
	font-weight: var(--weight-medium);
}

/* Sessions popover */
.sessions-menu {
	position: absolute;
	top: calc(100% + 6px);
	left: 0;
	z-index: 31;
	width: 300px;
	background: var(--surface-white);
	border: 1px solid var(--outline-gray-2);
	border-radius: var(--border-radius-md);
	box-shadow: var(--shadow-lg);
	display: flex;
	flex-direction: column;
	overflow: hidden;
}
.sessions-menu.right {
	left: auto;
	right: 0;
}
.sessions-head {
	display: flex;
	align-items: center;
	gap: 8px;
	padding: 9px 8px 9px 12px;
	border-bottom: 1px solid var(--outline-gray-1);
}
.sessions-head-title {
	flex: 1;
	font-size: var(--text-xs);
	font-weight: var(--weight-semibold);
	color: var(--ink-gray-7);
}
.sessions-close {
	flex: 0 0 auto;
	width: 22px;
	height: 22px;
	display: inline-flex;
	align-items: center;
	justify-content: center;
	padding: 0;
	border: 0;
	background: transparent;
	border-radius: 5px;
	color: var(--ink-gray-5);
	cursor: pointer;
}
.sessions-close:hover {
	background: var(--surface-gray-2);
	color: var(--ink-gray-8);
}
.sessions-list {
	max-height: 280px;
	overflow-y: auto;
	display: flex;
	flex-direction: column;
	padding: 4px;
}
.session-item {
	display: flex;
	align-items: center;
	gap: 10px;
	background: transparent;
	border: 0;
	cursor: pointer;
	text-align: left;
	padding: 8px 8px;
	border-radius: 6px;
	font-family: inherit;
	color: var(--ink-gray-9);
}
.session-item:hover {
	background: var(--surface-gray-2);
}
.session-title {
	flex: 1;
	min-width: 0;
	font-size: var(--text-sm);
	font-weight: var(--weight-regular);
	line-height: 1.4;
	white-space: nowrap;
	overflow: hidden;
	text-overflow: ellipsis;
}
.session-meta {
	flex: 0 0 auto;
	font-size: 11px;
	color: var(--ink-gray-5);
	white-space: nowrap;
}
.sessions-empty {
	padding: 16px 10px;
	font-size: var(--text-xs);
	color: var(--ink-gray-5);
	text-align: center;
}

/* Scrollbar */
.thin-scroll::-webkit-scrollbar {
	width: 8px;
	height: 8px;
}
.thin-scroll::-webkit-scrollbar-thumb {
	background: var(--gray-300);
	border-radius: 999px;
}
.thin-scroll::-webkit-scrollbar-track {
	background: transparent;
}
</style>
