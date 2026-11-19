<template>
	<div>
		<FormControl
			:model-value="modelValue || 'trigger'"
			type="select"
			variant="outline"
			:label="label"
			:options="options"
			@update:model-value="$emit('update:modelValue', $event)"
		/>
		<div class="mt-1 text-xs text-ink-gray-5">{{ hint }}</div>
	</div>
</template>

<script setup>
import { computed } from "vue";
import { FormControl } from "frappe-ui";
import { __ } from "frappe/i18n";

const props = defineProps({
	modelValue: { type: String, default: "trigger" },
	targets: { type: Array, default: () => [] },
	label: { type: String, default: "" },
});

defineEmits(["update:modelValue"]);

const options = computed(() =>
	props.targets.map((target) => ({
		label: target.doctype ? `${target.alias} (${target.doctype})` : target.alias,
		value: target.alias,
	}))
);

const hint = computed(() => {
	const target = props.targets.find((item) => item.alias === (props.modelValue || "trigger"));
	if (!target) return __("This alias is not available at this step");
	return target.doctype
		? __("One {0} record", [target.doctype])
		: __("DocType resolved at runtime");
});
</script>
