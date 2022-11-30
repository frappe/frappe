<script setup>
import { onMounted, ref } from "vue";

let props = defineProps(["df"]);

let map = ref(null);
let map_control = ref(null);

onMounted(() => {
	if (map.value) {
		map_control.value = frappe.ui.form.make_control({
			parent: map.value,
			df: { ...props.df, hidden: 0 },
			frm: true,
			disabled: true,
			render_input: true,
		});
	}
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
