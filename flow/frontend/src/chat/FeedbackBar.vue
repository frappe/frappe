<template>
	<span v-if="run && finished && !page.state.readOnly[sid]" class="flex items-center gap-0.5">
		<button
			class="flow-feedback-btn"
			:class="rating === 'Up' ? 'flow-feedback-selected' : ''"
			:title="rating === 'Up' ? 'Undo rating' : 'Good response'"
			:disabled="busy"
			@click="rate(rating === 'Up' ? 'None' : 'Up')"
		>
			<FeatherIcon name="thumbs-up" class="h-3.5 w-3.5" />
		</button>
		<button
			class="flow-feedback-btn"
			:class="rating === 'Down' ? 'flow-feedback-selected' : ''"
			:title="rating === 'Down' ? 'Undo rating' : 'Bad response'"
			:disabled="busy"
			@click="rating === 'Down' ? rate('None') : askWhy()"
		>
			<FeatherIcon name="thumbs-down" class="h-3.5 w-3.5" />
		</button>
	</span>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import { dialog, toast } from "frappe-ui";
import FeatherIcon from "@flow/ui-core/components/FeatherIcon.vue";

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
.flow-feedback-selected {
	color: var(--ink-gray-8);
}
.flow-feedback-selected :deep(svg) {
	fill: currentColor;
}
</style>
