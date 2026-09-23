<template>
	<div ref="host"></div>
</template>

<script setup>
import { useDeskWidget } from "../composables/useDeskWidget";

const props = defineProps({
	icon: { type: String, default: "" },
	title: { type: String, required: true },
	description: { type: String, default: "" },
});

const { host } = useDeskWidget(
	(el) =>
		frappe.ui
			.empty_state({
				icon: props.icon,
				title: props.title,
				description: props.description,
			})
			.appendTo(el),
	[() => props.icon, () => props.title, () => props.description]
);
</script>
