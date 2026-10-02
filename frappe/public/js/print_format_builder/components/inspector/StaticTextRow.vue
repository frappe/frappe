<template>
	<textarea
		class="form-control form-control-sm pfb-static-text-input"
		:placeholder="__('Write the text to print')"
		rows="4"
		:value="selected_field.text || ''"
		@input="(e) => (selected_field.text = e.target.value)"
	></textarea>
</template>

<script setup>
import { useSelectedField } from "./useSelectedField";

const { selected_field } = useSelectedField();
</script>
