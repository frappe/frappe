<script setup>
import EditableInput from "../EditableInput.vue";
import { useStore } from "../../store";
import { useSlots } from "vue";

let store = useStore();
let props = defineProps(["df", "value"]);
let slots = useSlots();

</script>

<template>
	<div v-if="!slots.actions" class="control">
		<div class="label" :class="{ reqd: df.reqd }">{{ df.label }}</div>
		<input
			class="form-control"
			type="text"
			:value="value"
			:disabled="store.read_only || df.read_only"
			@input="event => $emit('update:modelValue', event.target.value)"
		/>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
	<div class="control editable" v-else>
		<div class="field-controls">
			<EditableInput
				:class="{ reqd: df.reqd }"
				:text="df.label"
				:placeholder="__('Label')"
				:empty_label="`${__('No Label')} (${df.fieldtype})`"
				v-model="df.label"
			/>
			<slot name="actions"></slot>
		</div>
		<input
			class="form-control"
			type="text"
			disabled
		/>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>

<style lang="scss" scoped>
.label {
	margin-bottom: 0.3rem;
}

.editable input {
	background-color: var(--fg-color);
	cursor: pointer;
}

.reqd::after {
	content: " *";
	color: var(--red-400);
}

.label-actions {
	display: flex;
	justify-content: space-between;
	align-items: center;
}
</style>
