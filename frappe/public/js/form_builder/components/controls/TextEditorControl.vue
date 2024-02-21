<script setup>
import { computed, onMounted, ref } from "vue";

const props = defineProps(["df"]);

let quill = ref(null);
let quill_control = computed(() => {
	if (!quill.value) return;
	quill.value.innerHTML = "";

	return frappe.ui.form.make_control({
		parent: quill.value,
		df: { ...props.df, hidden: 0 },
		disabled: true,
		render_input: true,
		only_input: true,
	});
});

onMounted(() => {
	if (quill.value) quill_control.value;
});
</script>

<template>
	<div class="control editable">
		<div class="field-controls">
			<slot name="label" />
			<slot name="actions" />
		</div>
		<div class="quill" ref="quill"></div>
		<div v-if="df.description" class="mt-2 description" v-html="df.description"></div>
	</div>
</template>

<style lang="scss" scoped>
:deep(.quill) {
	.ql-toolbar {
		pointer-events: none;

		.ql-formats {
			margin-right: 12px;
		}
	}
	.ql-container p {
		cursor: pointer;
	}
}
</style>
