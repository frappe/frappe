<!-- Used as Text, Small Text & Long Text Control -->
<script setup>
import { useSlots, computed } from "vue";

const props = defineProps(["df", "value", "read_only", "modelValue"]);
let emit = defineEmits(["update:modelValue"]);
let slots = useSlots();

let height = computed(() => {
	if (props.df.fieldtype == "Small Text") {
		return "150px";
	}
	return "300px";
});
</script>

<template>
	<div class="control" :class="{ editable: slots.label }">
		<!-- label -->
		<div v-if="slots.label" class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div v-else class="control-label label">{{ __(df.label) }}</div>

		<!-- textarea input -->
		<textarea
			v-if="slots.label"
			:style="{ height: height, maxHeight: df.max_height ?? '' }"
			class="form-control"
			type="text"
			readonly
		/>
		<textarea
			v-else
			:style="{ height: height, maxHeight: df.max_height ?? '' }"
			class="form-control"
			type="text"
			:value="value"
			:disabled="read_only || df.read_only"
			@input="(event) => $emit('update:modelValue', event.target.value)"
		/>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>
