<script setup>
import { useSlots, onMounted, ref, computed, watch } from "vue";

const props = defineProps(["df", "read_only", "modelValue", "no_label"]);
let emit = defineEmits(["update:modelValue"]);
let slots = useSlots();

let select = ref(null);
let update_control = ref(true);

function get_options() {
	let options = props.df.options;

	if (typeof options == "string") {
		options = options.split("\n") || "";
		options = options.map((opt) => {
			return { label: __(opt), value: opt };
		});
	}

	if (options?.length && typeof options[0] == "string") {
		options = options.map((opt) => {
			return { label: __(opt), value: opt };
		});
	}

	if (props.df.fieldname == "fieldtype") {
		if (!in_list(frappe.model.layout_fields, props.modelValue)) {
			options =
				options &&
				options.filter((opt) => !in_list(frappe.model.layout_fields, opt.value));
		} else {
			options = [{ label: __(props.modelValue), value: props.modelValue }];
		}
	}

	if (props.df.sort_options) {
		options.sort((a, b) => a.label.localeCompare(b.label));
	}

	return options;
}

let select_control = computed(() => {
	if (!select.value) return;
	select.value.innerHTML = "";

	return frappe.ui.form.make_control({
		parent: select.value,
		df: {
			...props.df,
			fieldtype: "Select",
			hidden: 0,
			options: get_options(),
			read_only: Boolean(slots.label) || props.read_only,
			change: () => {
				if (update_control.value) {
					content.value = select_control.value.get_value();
				}
				update_control.value = true;
			},
		},
		value: content.value,
		render_input: true,
		only_input: Boolean(slots.label) || props.no_label,
	});
});

let content = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

onMounted(() => {
	if (select.value) select_control.value;
});

watch(
	() => content.value,
	(value) => {
		update_control.value = false;
		select_control.value?.set_value(value);
	}
);

watch(
	() => props.df.options,
	() => {
		select_control.value;
	}
);
</script>

<template>
	<div v-if="slots.label" class="control frappe-control" :class="{ editable: slots.label }">
		<!-- label -->
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>

		<!-- select input -->
		<div class="select-input">
			<input class="form-control" readonly />
			<div class="select-icon" v-html="frappe.utils.icon('select', 'sm')"></div>
		</div>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
	<div v-else class="control" ref="select"></div>
</template>

<style lang="scss" scoped>
.editable {
	.select-icon {
		top: 3px !important;
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
