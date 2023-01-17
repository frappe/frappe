<script setup>
import { onMounted, ref } from "vue";

let props = defineProps(["df"]);

let quill = ref(null);
let quill_control = ref(null);

onMounted(() => {
	if (quill.value) {
		quill_control.value = frappe.ui.form.make_control({
			parent: quill.value,
			df: { ...props.df, hidden: 0 },
			disabled: true,
			render_input: true,
			only_input: true,
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
