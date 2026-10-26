<template>
	<span v-if="run && finished && !page.state.readOnly[sid]" class="flex items-center gap-0.5">
		<button
			class="flow-feedback-btn"
			:class="rating === 'Up' ? 'flow-feedback-selected' : ''"
			:title="rating === 'Up' ? 'Undo rating' : 'Good response'"
			:disabled="busy"
			@click="rate(rating === 'Up' ? 'None' : 'Up')"
		>
			<svg class="size-3.5" viewBox="0 0 24 24" aria-hidden="true">
				<path
					d="M15 5.88 14 10h5.83a2 2 0 0 1 1.92 2.56l-2.33 8A2 2 0 0 1 17.5 22H4a2 2 0 0 1-2-2v-8a2 2 0 0 1 2-2h2.76a2 2 0 0 0 1.79-1.11L12 2a3.13 3.13 0 0 1 3 3.88Z"
				/>
				<path d="M7 10v12" />
			</svg>
		</button>
		<button
			class="flow-feedback-btn"
			:class="rating === 'Down' ? 'flow-feedback-selected' : ''"
			:title="rating === 'Down' ? 'Undo rating' : 'Bad response'"
			:disabled="busy"
			@click="rating === 'Down' ? rate('None') : askWhy()"
		>
			<svg class="size-3.5" viewBox="0 0 24 24" aria-hidden="true">
				<path
					d="M9 18.12 10 14H4.17a2 2 0 0 1-1.92-2.56l2.33-8A2 2 0 0 1 6.5 2H20a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2h-2.76a2 2 0 0 0-1.79 1.11L12 22a3.13 3.13 0 0 1-3-3.88Z"
				/>
				<path d="M17 14V2" />
			</svg>
		</button>
	</span>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import { dialog, toast } from "frappe-ui";

// Rendered by the core's message list after each finished turn (options.turnActions).
const props = defineProps({
	turnKey: { type: String, required: true },
	text: { type: String, default: "" },
	ts: { type: Number, default: null },
});
const flow = inject("flow");
const page = inject("flowPage");
const busy = ref(false);

const sid = computed(() => flow.state.sessionId);
const run = computed(() => (sid.value ? page.runForTurn(sid.value, props.turnKey) : null));
const finished = computed(() => ["Completed", "Denied", "Failed"].includes(run.value?.status));
const rating = computed(() => run.value?.feedback_rating || null);

function askWhy() {
	dialog.prompt({
		title: "What went wrong?",
		size: "lg",
		fields: [
			{
				name: "comment",
				type: "textarea",
				label: "Feedback",
				placeholder: "What went wrong? How should it respond instead?",
				defaultValue: run.value?.feedback_comment ?? "",
			},
		],
		confirmLabel: "Submit",
		onConfirm: ({ values }) => rate("Down", (values.comment ?? "").trim()),
	});
	focusComment();
}

// the prompt hands focus to the dialog's close button; the comment is what it is for,
// so claim the field once it mounts
function focusComment(tries = 20) {
	const field = [...document.querySelectorAll("[role=dialog] textarea")].at(-1);
	if (field) field.focus();
	else if (tries) requestAnimationFrame(() => focusComment(tries - 1));
}

// a thumbs-down comment becomes agent memory server-side; the toast says so
async function rate(value, comment = "") {
	if (busy.value || !run.value) return;
	busy.value = true;
	const session = sid.value;
	const name = run.value.name;
	try {
		const result = await flow.client.submitFeedback(name, value, comment);
		page.updateRun(session, name, {
			feedback_rating: result.rating ?? "",
			feedback_comment: value === "Down" ? comment : "",
		});
		if (result.memory) toast.success("Saved to agent memory.");
		else if (result.forgotten) toast.success("Removed from agent memory.");
	} catch (error) {
		toast.error(error?.message ?? "Could not save feedback.");
	} finally {
		busy.value = false;
	}
}
</script>

<style scoped>
.flow-feedback-btn {
	display: grid;
	place-items: center;
	width: 24px;
	height: 24px;
	border-radius: 5px;
	color: var(--ink-gray-4);
	background: transparent;
}
.flow-feedback-btn:hover {
	background: var(--surface-gray-2);
	color: var(--ink-gray-8);
}
.flow-feedback-btn:disabled {
	opacity: 0.5;
	pointer-events: none;
}
/* Lucide's thumbs, drawn inline: a lucide-* class is a mask, which can't fill once rated */
.flow-feedback-btn svg {
	fill: none;
	stroke: currentColor;
	stroke-width: 1.5;
	stroke-linecap: round;
	stroke-linejoin: round;
}
.flow-feedback-selected {
	color: var(--ink-gray-8);
}
.flow-feedback-selected :deep(svg) {
	fill: currentColor;
}
</style>
