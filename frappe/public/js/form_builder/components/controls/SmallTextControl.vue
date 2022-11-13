<script setup>
import { useStore } from "../../store";
import { useSlots } from "vue";

let store = useStore();
let props = defineProps(["df", "value"]);
let slots = useSlots();
</script>

<template>
	<div class="control" :class="{ editable: slots.label }">
		<!-- label -->
		<div v-if="slots.label" class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div v-else class="label">{{ df.label }}</div>

		<!-- textarea input -->
		<textarea v-if="slots.label" class="form-control" type="text" disabled />
		<textarea
			v-else
			class="form-control"
			type="text"
			:value="value"
			:disabled="store.read_only || df.read_only"
			@input="event => $emit('update:modelValue', event.target.value)"
		/>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>
