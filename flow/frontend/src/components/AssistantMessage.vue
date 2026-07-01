<script setup>
import { computed } from "vue";
import MarkdownText from "./MarkdownText.vue";
import ActivityGroup from "./ActivityGroup.vue";
import ConfirmCard from "./ConfirmCard.vue";
import WorkingIndicator from "./WorkingIndicator.vue";
import { useStore } from "@/store";

const props = defineProps({ message: { type: Object, required: true } });
const { answerQuestion, toolApproval } = useStore();

const questionByKey = computed(() => new Map(props.message.questions.map((q) => [q.key, q])));

// A confirmation tool (per the agent's tool map), or one that has/had a question.
function isApproval(part) {
	const q = questionByKey.value.get(part.id);
	return toolApproval.value[part.name] === true || q !== undefined || part.approval !== null;
}

// Group parts for render: text → prose, approval tool → own line (card if pending),
// other tools → merged activity group. Rendering-only.
const items = computed(() => {
	const out = [];
	for (const part of props.message.parts) {
		if (part.type !== "tool") {
			out.push({ kind: "text", id: part.id, part });
			continue;
		}
		if (isApproval(part)) {
			const q = questionByKey.value.get(part.id);
			if (q && q._answer === undefined)
				out.push({ kind: "confirm", id: part.id, question: q, part });
			else out.push({ kind: "approval", id: part.id, parts: [part] });
			continue;
		}
		const last = out[out.length - 1];
		if (last?.kind === "activity") last.parts.push(part);
		else out.push({ kind: "activity", id: part.id, parts: [part] });
	}
	return out;
});

// Standalone "Thinking…" only until the first response part arrives; later thinking
// shows inline as the activity group's label.
const showWorking = computed(() => props.message.pending && !props.message.parts.length);
</script>

<template>
	<div class="flow-parts flex flex-col">
		<template v-for="(item, i) in items" :key="item.id">
			<MarkdownText v-if="item.kind === 'text'" :part="item.part" />
			<ConfirmCard
				v-else-if="item.kind === 'confirm'"
				:question="item.question"
				:tool="item.part"
				@answer="(answer) => answerQuestion(item.question, answer)"
			/>
			<ActivityGroup
				v-else
				:parts="item.parts"
				:sealed="i < items.length - 1"
				:live="message.pending"
			/>
		</template>

		<WorkingIndicator v-if="showWorking" />
	</div>
</template>
