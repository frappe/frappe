<script setup>
import { computed, onMounted, ref, watch } from "vue";

const props = defineProps(["df"]);

let rating = ref(null);
let rating_control = computed(() => {
	if (!rating.value) return;
	rating.value.innerHTML = "";

	return frappe.ui.form.make_control({
		parent: rating.value,
		df: { ...props.df, hidden: 0 },
		disabled: true,
		render_input: true,
		only_input: true,
	});
});

onMounted(() => {
	if (rating.value) rating_control.value;
});

watch(
	() => props.df.options,
	(value) => {
		if (rating_control.value) {
			rating_control.value.df.options = value;
			rating_control.value?.make_input();
		}
	}
);
</script>

<template>
	<div class="control editable">
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div ref="rating"></div>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>

<style lang="scss" scoped>
:deep(.rating) {
	--star-fill: var(--yellow-300) !important;
}
</style>
