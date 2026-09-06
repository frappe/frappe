<!--
  A row's leading word: "Where" on the first row, the group's operator on every
  row after it. The cell around it belongs to the row; this renders the word.

  A group holds one operator, so exactly one cell is a control. The repeats are
  text, not disabled buttons: a disabled control is skipped in a screen reader's
  forms mode and exempt from the contrast minimum. Which is why they are
  ink-gray-6, not the cell's ink-gray-5, which is 4.18:1 on white and misses
  1.4.3 at 14px.
-->
<template>
	<div class="text-p-base text-ink-gray-5">
		<div v-if="index === 0">{{ labels.where }}</div>
		<template v-else>
			<Button
				v-if="canToggle"
				variant="subtle"
				class="w-max"
				iconRight="lucide-refresh-cw"
				:label="word"
				:aria-describedby="hintId"
				@click="toggle"
			/>
			<div v-else class="text-ink-gray-6">{{ word }}</div>
			<span v-if="canToggle" :id="hintId" class="sr-only">
				{{ labels.conjunctionHint }}
			</span>
		</template>
	</div>
</template>

<script setup lang="ts">
import { computed, useId } from "vue";
import { Button } from "frappe-ui";
import { useConditionBuilderContext } from "./internal/context";
import type { ConditionPath, Conjunction } from "./types";

const props = defineProps<{
	index: number;
	conjunction: Conjunction;
	groupPath: ConditionPath;

	/** Whether this cell's control is live. Decided by the group, not here. */
	canToggle?: boolean;
}>();

const context = useConditionBuilderContext();
const labels = context.labels;
const hintId = useId();

function toggle() {
	context.setConjunction(props.groupPath, props.conjunction === "and" ? "or" : "and");
}

const word = computed(() => (props.conjunction === "and" ? labels.value.and : labels.value.or));
</script>
