<script setup>
import { computed } from "vue";
import MarkdownText from "./MarkdownText.vue";
import ToolCall from "./ToolCall.vue";
import ConfirmCard from "./ConfirmCard.vue";
import WorkingIndicator from "./WorkingIndicator.vue";
import { useStore } from "@/store";
import { __ } from "@/lib/translate";

const props = defineProps({ message: { type: Object, required: true } });
const { answerQuestion } = useStore();

const lastPart = computed(() => props.message.parts[props.message.parts.length - 1]);
const toolRunning = computed(
	() => lastPart.value?.type === "tool" && lastPart.value.result === null
);
// While a tool is running it shows its own spinner; otherwise show the dots.
const showWorking = computed(() => props.message.pending && !toolRunning.value);
const workingLabel = computed(() => (props.message.parts.length ? "" : __("Thinking…")));

// A tool is awaiting approval when an unanswered question targets its id.
function isAwaiting(toolId) {
	return props.message.questions.some((q) => q.key === toolId && q._answer === undefined);
}
</script>

<template>
	<div class="flow-parts flex flex-col">
		<template v-for="part in message.parts" :key="part.id">
			<MarkdownText v-if="part.type === 'text'" :part="part" />
			<ToolCall v-else :part="part" :awaiting-approval="isAwaiting(part.id)" />
		</template>

		<WorkingIndicator v-if="showWorking" :label="workingLabel" />

		<div v-if="message.questions.length" class="flex flex-col gap-2">
			<ConfirmCard
				v-for="q in message.questions"
				:key="q.key"
				:question="q"
				@answer="(answer) => answerQuestion(q, answer)"
			/>
		</div>
	</div>
</template>
