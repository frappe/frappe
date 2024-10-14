<script setup>
import { useSlots, onMounted, ref, computed, watch } from "vue";
const props = defineProps(["df", "read_only", "modelValue", "no_label"]);
let emit = defineEmits(["update:modelValue"]);
let slots = useSlots();
let radio = ref(null);
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
	// Check for allow_others property
	if (props.df.allow_others) {
		options.push({ label: "Others", value: "others" });
	}

	return options;
}
let radio_control = computed(() => {
	if (!radio.value) return;
	radio.value.innerHTML = "";
	return frappe.ui.form.make_control({
		parent: radio.value,
		df: {
			...props.df,
			fieldtype: "Radio",
			hidden: 0,
			options: get_options(),
			read_only: Boolean(slots.label) || props.read_only,
			change: () => {
				if (update_control.value) {
					content.value = radio_control.value.get_value();
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
	if (radio.value) radio_control.value;
});
watch(
	() => content.value,
	(value) => {
		update_control.value = false;
		radio_control.value?.set_value(value);
	}
);
watch(
	() => props.df.options,
	() => {
		radio_control.value;
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
		<!-- radio inputs -->
		<div class="radio-inputs">
			<div v-for="option in get_options()" :key="option.value" class="form-check">
				<input
					type="radio"
					:value="option.value"
					v-model="content"
					:disabled="true"
					:checked="content === option.value"
					:id="option.value"
					class="form-check-input"
				/>
				<label class="form-check-label" :for="option.value">{{ option.label }}</label>
			</div>
		</div>
		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
	<div v-else class="control" ref="radio"></div>
</template>
<style lang="scss" scoped>
.editable {
	.radio-inputs {
		margin-bottom: 10px;
	}
}
.radio-inputs {
	.form-check {
		margin-bottom: 5px;
	}
}
</style>
