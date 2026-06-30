<script setup>
import { ref, computed, nextTick } from "vue";
import { Button, FeatherIcon } from "@/lib/ui";
import ArgsView from "./ArgsView.vue";
import { toolLabel, argEntries } from "@/lib/toolMeta";
import { __ } from "@/lib/translate";

const props = defineProps({
	question: { type: Object, required: true },
	tool: { type: Object, default: null },
});
const emit = defineEmits(["answer"]);

const otherEl = ref(null);

// Prompt is "Approve `tool`?\n\n<summary>[\n\n<detail>]". Show the summary (or tool
// label) as title and render args readably, dropping the prompt's JSON tail.
const paras = computed(() => props.question.prompt.split("\n\n"));
const looksJson = (s) => /^\s*[{[]/.test(s || "");

const title = computed(() => {
	if (props.tool) {
		const summary = (paras.value[1] || "").replace(/`/g, "").replace(/:$/, "").trim();
		return summary && !looksJson(summary) ? summary : toolLabel(props.tool.name);
	}
	return (paras.value[0] || "").replace(/`/g, "").trim();
});

// A free-text (non-tool) question keeps its prose body; tool args replace any body.
const body = computed(() => (props.tool ? "" : paras.value.slice(1).join("\n\n").trim()));
const hasArgs = computed(() => props.tool && argEntries(props.tool.arguments).length > 0);
const answered = computed(() => props.question._answer !== undefined);

function pick(option) {
	emit("answer", option);
}
function showOther() {
	props.question._showOther = true;
	nextTick(() => otherEl.value?.focus());
}
function cancelOther() {
	props.question._showOther = false;
	props.question._otherText = "";
}
function sendOther() {
	const text = props.question._otherText?.trim();
	if (text) emit("answer", text);
}
</script>

<template>
	<div
		class="rounded-lg border border-outline-gray-2 bg-surface-white p-2.5"
		:class="{ 'opacity-70': answered }"
	>
		<div class="flex items-center gap-2">
			<span
				class="flex h-5 w-5 shrink-0 items-center justify-center rounded-md bg-surface-gray-2 text-ink-gray-7"
			>
				<FeatherIcon name="shield" class="h-3.5 w-3.5" />
			</span>
			<div class="break-words text-sm font-medium leading-snug text-ink-gray-9">
				{{ title }}
			</div>
		</div>

		<div v-if="hasArgs" class="mt-2.5">
			<ArgsView :arguments="tool.arguments" />
		</div>
		<pre v-else-if="body" class="flow-confirm-body">{{ body }}</pre>

		<div
			v-if="answered"
			class="mt-2 flex items-center justify-end gap-1.5 text-xs text-ink-gray-6"
		>
			<FeatherIcon name="check" class="h-3 w-3" />
			<span class="truncate">{{ question._answer }}</span>
		</div>

		<template v-else>
			<div v-if="!question._showOther" class="mt-2.5 flex flex-wrap justify-end gap-1.5">
				<Button
					v-for="opt in question.options"
					:key="opt"
					:variant="opt === 'Approve' ? 'solid' : 'outline'"
					theme="gray"
					:label="opt"
					@click="pick(opt)"
				/>
				<Button
					v-if="question.allow_other !== false"
					variant="ghost"
					:label="__('Other…')"
					@click="showOther"
				/>
			</div>

			<div v-else class="mt-2.5">
				<textarea
					ref="otherEl"
					v-model="question._otherText"
					rows="2"
					class="w-full resize-none rounded-md border border-outline-gray-2 bg-surface-white px-2.5 py-2 text-sm text-ink-gray-9 outline-none focus:border-outline-gray-3"
					:placeholder="__('Describe what you want instead…')"
					@keydown.enter.exact.prevent="sendOther"
					@keydown.esc="cancelOther"
				></textarea>
				<div class="mt-1.5 flex justify-end gap-1.5">
					<Button variant="ghost" :label="__('Cancel')" @click="cancelOther" />
					<Button
						variant="solid"
						theme="gray"
						:label="__('Send')"
						:disabled="!question._otherText?.trim()"
						@click="sendOther"
					/>
				</div>
			</div>
		</template>
	</div>
</template>

<style scoped>
.flow-confirm-body {
	margin: 8px 0 0;
	padding: 8px 10px;
	max-height: 220px;
	overflow: auto;
	background: var(--surface-gray-1);
	border: 1px solid var(--outline-gray-1);
	border-radius: 6px;
	font-family: var(--font-stack-monospace, ui-monospace, monospace);
	font-size: 11.5px;
	line-height: 1.55;
	color: var(--ink-gray-8);
	white-space: pre-wrap;
	word-break: break-word;
}
</style>
