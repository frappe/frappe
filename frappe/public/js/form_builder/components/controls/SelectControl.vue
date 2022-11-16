<script setup>
import { useStore } from "../../store";
import { useSlots } from "vue";

let store = useStore();
let props = defineProps(["df", "value"]);
let slots = useSlots();

function get_options() {
	let options = props.df.options?.split("\n") || "";

	if (props.value) {
		if (
			props.df.fieldname == "fieldtype" &&
			!in_list(frappe.model.layout_fields, props.value)
		) {
			return options && options.filter(opt => !in_list(frappe.model.layout_fields, opt));
		} else {
			return [props.value];
		}
	}

	return options;
}
</script>

<template>
	<div class="control" :class="{ editable: slots.label }">
		<!-- label -->
		<div v-if="slots.label" class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div v-else class="label" :class="{ reqd: df.reqd }">{{ df.label }}</div>

		<!-- select input -->
		<div v-if="slots.label" class="select-input">
			<input class="form-control" disabled />
			<div class="select-icon" v-html="frappe.utils.icon('select', 'sm')"></div>
		</div>
		<div v-else class="select-input">
			<select
				class="form-control"
				v-model="value"
				:disabled="store.read_only || df.read_only"
				@change="event => $emit('update:modelValue', event.target.value)"
			>
				<option v-for="option in get_options()" :key="option" :value="option">{{
					option
				}}</option>
			</select>
			<div class="select-icon" v-html="frappe.utils.icon('select', 'sm')"></div>
		</div>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>

<style lang="scss" scoped>
.editable {
	.select-icon {
		top: 7px !important;
	}
}

.select-input {
	position: relative;

	.select-icon {
		position: absolute;
		pointer-events: none;
		top: 5px;
		right: 10px;
	}
}
</style>
