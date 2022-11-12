<script setup>
import EditableInput from "../EditableInput.vue";
import { useStore } from "../../store";
import { useSlots } from "vue";

let store = useStore();
let props = defineProps(["df", "value"]);
let slots = useSlots();

</script>

<template>
	<div v-if="!slots.actions" class="control checkbox">
		<label>
			<input
				type="checkbox"
				:checked="value"
				:disabled="store.read_only || df.read_only"
				@change="event => $emit('update:modelValue', event.target.checked)"
			/>
			<span class="label-area" :class="{ reqd: df.reqd }">{{ df.label }}</span>
		</label>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
	<div class="control checkbox editable" v-else>
		<label class="field-controls">
			<div class="checkbox">
				<input type="checkbox" disabled />
				<EditableInput
					:class="{ reqd: df.reqd }"
					:text="df.label"
					:placeholder="__('Label')"
					:empty_label="`${__('No Label')} (${df.fieldtype})`"
					v-model="df.label"
				/>
			</div>
			<slot name="actions"></slot>
		</label>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>

<style lang="scss" scoped>
label, input {
	margin-bottom: 0 !important;
	cursor: pointer;
}

label .checkbox {
	display: flex;
	align-items: center;

	input {
		background-color: var(--fg-color);
		box-shadow: none;
		border: 1px solid var(--gray-400);
		pointer-events: none;
	}
}
</style>
