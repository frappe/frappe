<script setup>
import { computed, onBeforeUnmount, onMounted, ref, toRef } from "vue";
import Card from "../../widget_type/card/card.vue";
import Shortcut from "../../widget_type/shortcut/shortcut.vue";
import { provide_widget_state } from "./widget.js";

// A Widget block: frappe's own types draw in this page, an app's type through its island.
const props = defineProps({
	widget: { type: Object, required: true },
	island: { type: String, required: true },
});

const BUILT_IN = {
	"frappe.widget.shortcut": Shortcut,
	"frappe.widget.card": Card,
};

const widget = toRef(props, "widget");
const data = computed(() => props.widget.data);
const state = provide_widget_state({ widget, data });

const component = computed(() => BUILT_IN[props.island]);
const host = ref(null);
let mounted = null;

onMounted(() => {
	if (component.value) return;
	mounted = window.frappe.ui.mount_island(props.island, host.value, { widget: state });
});
onBeforeUnmount(() => mounted?.unmount());
</script>

<template>
	<component :is="component" v-if="component" />
	<div v-else ref="host" class="h-full" />
</template>
