<script setup>
import { ref, computed, nextTick } from "vue";
import { Button, FeatherIcon } from "@/lib/ui";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";

const props = defineProps({
	message: { type: Object, required: true },
	hovered: { type: Boolean, default: false },
});
const { submitFeedback } = useStore();

const COMMENT_LIMIT = 500;

const open = ref(false);
const comment = ref("");
const submitting = ref(false);
const commentEl = ref(null);

const rating = computed(() => props.message.feedback?.rating || null);
// Hidden until hover; stays visible once rated or while the comment form is open.
const visible = computed(() => props.hovered || Boolean(rating.value) || open.value);

// Re-clicking the active thumb clears it; clicking the other switches.
async function rateUp() {
	open.value = false;
	await submit(rating.value === "Up" ? "None" : "Up");
}

async function rateDown() {
	if (rating.value === "Down") {
		await submit("None");
		return;
	}
	comment.value = props.message.feedback?.comment || "";
	open.value = true;
	nextTick(() => commentEl.value?.focus());
}

function cancel() {
	open.value = false;
	comment.value = "";
}

async function sendDown() {
	await submit("Down", comment.value.trim());
	open.value = false;
}

// A Down comment is turned into agent memory server-side; the toast reflects that.
async function submit(value, text = "") {
	if (submitting.value) return;
	submitting.value = true;
	try {
		const result = await submitFeedback(props.message, value, text);
		if (result?.memory) {
			frappe.show_alert({ message: __("Saved to agent memory."), indicator: "green" });
		}
	} catch (e) {
		frappe.show_alert({
			message: e?.message || __("Could not save feedback."),
			indicator: "red",
		});
	} finally {
		submitting.value = false;
	}
}
</script>

<template>
	<div class="mt-1">
		<div
			class="flex items-center gap-0.5 transition-opacity duration-150"
			:class="visible ? 'opacity-100' : 'pointer-events-none opacity-0'"
		>
			<button
				type="button"
				class="flow-feedback-btn"
				:class="{ 'flow-feedback-selected': rating === 'Up' }"
				:disabled="submitting"
				:title="rating === 'Up' ? __('Undo rating') : __('Good response')"
				@click="rateUp"
			>
				<FeatherIcon name="thumbs-up" class="h-4 w-4" />
			</button>
			<button
				type="button"
				class="flow-feedback-btn"
				:class="{ 'flow-feedback-selected': rating === 'Down' }"
				:disabled="submitting"
				:title="rating === 'Down' ? __('Undo rating') : __('Bad response')"
				@click="rateDown"
			>
				<FeatherIcon name="thumbs-down" class="h-4 w-4" />
			</button>
		</div>

		<div
			v-if="open"
			class="mt-1.5 rounded-lg border border-outline-gray-2 bg-surface-white p-2.5"
		>
			<textarea
				ref="commentEl"
				v-model="comment"
				rows="2"
				:maxlength="COMMENT_LIMIT"
				class="flow-textarea w-full resize-none rounded-md border border-outline-gray-2 bg-surface-white px-2.5 py-2 text-sm text-ink-gray-9 outline-none focus:border-outline-gray-3"
				:placeholder="__('What went wrong? How should it respond instead?')"
				@keydown.esc="cancel"
			></textarea>
			<div class="mt-1.5 flex justify-end gap-1.5">
				<Button variant="ghost" :label="__('Cancel')" @click="cancel" />
				<Button
					variant="solid"
					theme="gray"
					:label="__('Submit')"
					:disabled="submitting"
					@click="sendDown"
				/>
			</div>
		</div>
	</div>
</template>

<style scoped>
.flow-feedback-btn {
	display: flex;
	align-items: center;
	justify-content: center;
	height: 30px;
	width: 30px;
	border-radius: 7px;
	color: var(--ink-gray-5);
	background: transparent;
}
.flow-feedback-btn:hover {
	background: var(--surface-gray-2);
	color: var(--ink-gray-7);
}
.flow-feedback-btn:disabled {
	opacity: 0.5;
	pointer-events: none;
}
/* Feedback given: fill the icon in a mid-dark gray, over a lighter background. */
.flow-feedback-selected {
	background: var(--surface-gray-2);
	color: var(--ink-gray-7);
}
.flow-feedback-selected :deep(svg) {
	fill: currentColor;
}
/* Kill the desk's global blue focus ring on the comment box. */
.flow-textarea:focus {
	border-color: var(--outline-gray-3);
	box-shadow: none;
	outline: none;
}
</style>
