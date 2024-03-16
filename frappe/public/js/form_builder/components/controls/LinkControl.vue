<!-- Used as Link Control -->
<script setup>
import { onMounted, ref, useSlots, computed, watch } from "vue";

const props = defineProps(["args", "df", "read_only", "modelValue"]);
let emit = defineEmits(["update:modelValue"]);
let slots = useSlots();

let link = ref(null);
let update_control = ref(true);

let link_control = computed(() => {
	if (!link.value) return;
	link.value.innerHTML = "";

	return frappe.ui.form.make_control({
		parent: link.value,
		df: {
			...props.df,
			hidden: 0,
			read_only: Boolean(slots.label) || props.read_only,
			change: () => {
				if (update_control.value) {
					content.value = link_control.value.get_value();
				}
				update_control.value = true;
			},
		},
		value: content.value,
		render_input: true,
		only_input: Boolean(slots.label),
	});
});

let content = computed({
	get: () => props.modelValue,
	set: (value) => emit("update:modelValue", value),
});

onMounted(() => {
	if (link.value) {
		if (props.args?.is_table_field) {
			if (props.df.filters) {
				// update filters
				props.df.filters.istable = 1;
			} else {
				// add filters
				props.df.filters = { istable: 1 };
			}
		} else {
			// reset filters
			if (props.df.filters && "istable" in props.df.filters) {
				delete props.df.filters.istable;
			}
		}

		link_control.value;
	}
});

watch(
	() => content.value,
	(value) => {
		update_control.value = false;
		link_control.value?.set_value(value);
	}
);
</script>

<template>
	<div
		v-if="slots.label"
		class="control frappe-control"
		:data-fieldtype="df.fieldtype"
		:class="{ editable: slots.label }"
	>
		<!-- label -->
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>

		<!-- link input -->
		<input class="form-control" type="text" readonly />

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description" />
	</div>
	<div v-else ref="link"></div>
</template>
