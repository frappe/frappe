<!--
  One leaf's slot boundary: the consumer's `#condition`, or the built-in editor.
  `ConditionLeaf` is a subgrid, so its three cells sit in the row's three middle
  tracks. A custom `#condition` gets one box spanning the same three.
-->
<template>
	<div
		v-if="$slots.condition"
		data-slot="condition-row"
		class="min-w-0"
		style="grid-column: span 3"
	>
		<slot
			name="condition"
			:condition="condition"
			:path="path"
			:depth="depth"
			:readonly="readonly"
			:update="update"
		/>
	</div>

	<ConditionLeaf
		v-else
		:condition="condition as FieldConditionValue"
		:field-label-id="fieldLabelId"
		@update="update"
	>
		<template v-if="$slots['condition-value']" #condition-value="valueProps">
			<slot name="condition-value" v-bind="valueProps" />
		</template>
	</ConditionLeaf>
</template>

<script setup lang="ts">
import { computed } from "vue";
import ConditionLeaf from "./ConditionLeaf.vue";
import { useConditionBuilderContext } from "./internal/context";
import type {
	ConditionPath,
	ConditionSlotProps,
	FieldConditionValue,
	ValueSlotProps,
} from "./types";

const props = defineProps<{
	condition: unknown;
	path: ConditionPath;

	/** Id of the element holding this row's field label, rendered by the row. */
	fieldLabelId?: string;
}>();

defineSlots<{
	condition?(props: ConditionSlotProps<unknown>): unknown;
	"condition-value"?(props: ValueSlotProps): unknown;
}>();

const context = useConditionBuilderContext();

const depth = computed(() => props.path.length);
const readonly = computed(() => context.readonly.value);

function update(value: unknown) {
	context.update(props.path, value);
}
</script>
