<!-- The marks that follow a field's label on the canvas: "· Title field", a rule mark, and in Customize
     what the site did. A word joiner ties the first mark to the label's last word, so they wrap together. -->
<template>
	<span
		v-if="titled || ruled || customized"
		class="-my-0.5 ml-1 inline-flex items-center gap-1 whitespace-nowrap align-baseline [[data-slot=label-after]_&]:ml-0"
		:class="{ '[&_.lucide-split]:text-ink-gray-9': hidden }"
		data-canvas-marks
	>
		<span class="-mr-1 [[data-slot=label-after]_&]:hidden" aria-hidden="true">&#8288;</span>
		<span
			v-if="titled"
			:class="hidden ? 'text-ink-gray-9' : 'text-ink-gray-6'"
			data-canvas-mark="title"
			>{{ __("· Title field") }}</span
		>
		<RuleMark :canvas="canvas" kind="field" :node="canvas.field(fieldname)" />
		<CustomizeMarks :canvas="canvas" :fieldname="fieldname" />
	</span>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { __ } from "@/i18n";
import CustomizeMarks from "./CustomizeMarks.vue";
import type { DesignCanvas } from "./designCanvas";
import RuleMark from "./RuleMark.vue";
import { FIELD_RULES } from "./ruleRows";
import { RuleWords } from "./ruleWords";

const props = defineProps<{ canvas: DesignCanvas; fieldname: string }>();

const titled = computed(
	() => props.canvas.working.value.settings.properties.title_field === props.fieldname,
);
const ruled = computed(() => {
	const node = props.canvas.field(props.fieldname);
	return !!node && RuleWords.of(props.canvas).lines(FIELD_RULES, node).length > 0;
});
const hidden = computed(() => !!props.canvas.customize?.marks(props.fieldname)?.hidden);
const customized = computed(() => {
	const marks = props.canvas.customize?.marks(props.fieldname);
	return !!marks && (marks.hidden || marks.custom || marks.changed.length > 0);
});
</script>
