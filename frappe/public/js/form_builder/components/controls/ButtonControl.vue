<!-- Used as Button & Heading Control -->
<script setup>
import { computed } from "vue";

const props = defineProps(["df", "value"]);

const button_class = computed(() => {
	const color_map = {
		Default: "btn-default",
		Primary: "btn-primary",
		Info: "btn-info",
		Success: "btn-success",
		Warning: "btn-warning",
		Danger: "btn-danger",
	};
	const color = props.df.button_color ?? "Default";

	return `btn btn-xs ${color_map[color] || color_map.Default}`;
});
</script>

<template>
	<div class="control frappe-control editable" :data-fieldtype="df.fieldtype">
		<!-- label -->
		<div class="field-controls">
			<h4 v-if="df.fieldtype == 'Heading'">
				<slot name="label" />
			</h4>
			<button v-else :class="button_class">
				<slot name="label" />
			</button>
			<slot name="actions" />
		</div>

		<!-- description -->
		<div v-if="df.description" class="mt-2 description" v-html="df.description" />
	</div>
</template>

<style lang="scss" scoped>
h4 {
	margin-bottom: 0px;
}
</style>
