<script setup>
import { computed, onMounted, ref } from "vue";

const props = defineProps(["df"]);

let map = ref(null);
let map_control = computed(() => {
	if (!map.value) return;
	map.value.innerHTML = "";

	return frappe.ui.form.make_control({
		parent: map.value,
		df: { ...props.df, hidden: 0 },
		frm: true,
		disabled: true,
		render_input: true,
	});
});

onMounted(() => {
	if (map.value) map_control.value;
});
</script>

<template>
	<div class="control editable">
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div ref="map"></div>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>

<style lang="scss" scoped>
:deep(.clearfix) {
	display: none;
}
</style>
