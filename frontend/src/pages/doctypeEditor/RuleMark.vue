<!-- A small gray mark on a field, section, column or tab that has a rule; its Tooltip says each rule
     in words. The host positions it so it takes no layout width. -->
<template>
	<span
		v-if="lines.length"
		class="inline-grid size-4 shrink-0 place-items-center align-middle"
		data-rule-mark
	>
		<Tooltip>
			<template #content>
				<div class="max-w-[320px] space-y-1 whitespace-normal break-words">
					<p v-for="line in lines" :key="line">{{ line }}</p>
				</div>
			</template>
			<span
				class="lucide-split size-3.5 text-ink-gray-5"
				role="img"
				:aria-label="lines.join(' · ')"
			/>
		</Tooltip>
	</span>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { Tooltip } from "frappe-ui";
import type { DesignCanvas } from "./designCanvas";
import { containerRules, FIELD_RULES } from "./ruleRows";
import { RuleWords } from "./ruleWords";

const props = defineProps<{
	canvas: DesignCanvas;
	kind: "field" | "tab" | "section" | "column";
	node: object | null | undefined;
}>();

const lines = computed(() => {
	const { kind, node } = props;
	if (!node) return [];
	const rules = kind === "field" ? FIELD_RULES : containerRules(kind, node);
	return RuleWords.of(props.canvas).lines(rules, node);
});
</script>
