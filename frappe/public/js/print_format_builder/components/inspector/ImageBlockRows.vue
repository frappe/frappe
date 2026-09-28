<template>
	<ImageUploadControl
		:model-value="selected_field.image_url"
		:alt="selected_field.label"
		@update:model-value="set_image_url"
	/>
	<SizeRow
		v-if="selected_field.image_url"
		:label="__('Size')"
		:model-value="selected_field.width"
		@update:model-value="(v) => (selected_field.width = v)"
	/>
</template>

<script setup>
import ImageUploadControl from "./ImageUploadControl.vue";
import SizeRow from "./SizeRow.vue";
import { get_image_dimensions } from "../../utils";
import { useSelectedField } from "./useSelectedField";

const { selected_field } = useSelectedField();

function set_image_url(url) {
	selected_field.value.image_url = url;
	if (!url) {
		selected_field.value.width = "";
		return;
	}
	get_image_dimensions(url)
		.then(({ width }) => {
			if (!parseFloat(selected_field.value.width)) {
				selected_field.value.width = Math.min(width, 300) + "px";
			}
		})
		.catch(() => {});
}
</script>
