<script setup>
import { onBeforeUnmount, onMounted, ref, toRef, watch } from "vue";
import Card from "../../widget_type/card/card.vue";
import NumberCard from "../../widget_type/number_card/number_card.vue";
import Shortcut from "../../widget_type/shortcut/shortcut.vue";
import { post } from "./api.js";
import { provide_widget_state } from "./widget.js";

// A Widget block: frappe's own types draw in this page, an app's type through its island.
const props = defineProps({
	widget: { type: Object, required: true },
	island: { type: String, required: true },
});

const BUILT_IN = {
	"frappe.widget.shortcut": Shortcut,
	"frappe.widget.card": Card,
	"frappe.widget.number_card": NumberCard,
};

const data = ref(props.widget.data);
const loading = ref(false);
const error = ref(null);
const filters = ref({});
watch(
	() => props.widget.data,
	(fresh) => (data.value = fresh)
);

// the reader's own filters, for their view only
async function load() {
	const name = props.widget.name;
	loading.value = true;
	error.value = null;
	try {
		const fresh = await post("frappe.desk.widgets.refresh", {
			names: [name],
			filters: { [name]: filters.value },
		});
		data.value = fresh[name]?.data ?? null;
	} catch (e) {
		error.value = e;
	} finally {
		loading.value = false;
	}
}

const state = provide_widget_state({
	widget: toRef(props, "widget"),
	data,
	loading,
	error,
	filters,
	setFilters: (values) => {
		filters.value = { ...filters.value, ...values };
		return load();
	},
	refresh: load,
});

const component = BUILT_IN[props.island];
const host = ref(null);
let mounted = null;

onMounted(() => {
	if (component) return;
	mounted = window.frappe.ui.mount_island(props.island, host.value, { widget: state });
});
onBeforeUnmount(() => mounted?.unmount());
</script>

<template>
	<component :is="component" v-if="component" />
	<div v-else ref="host" class="h-full" />
</template>
