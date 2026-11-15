<script setup>
import { computed } from "vue";
import Card from "../../../widget_type/card/card.vue";
import { provide_widget_state } from "../widget.js";

// An old label-keyed card, drawn by the Card widget's renderer.
const props = defineProps({
	widget: { type: Object, required: true },
});

provide_widget_state({
	widget: computed(() => ({ label: props.widget.label, config: props.widget })),
	data: computed(() => ({ items: props.widget.links })),
});
</script>

<template>
	<Card />
</template>
