<!-- One text of a layout to change, its title or its condition; it closes with the new text. -->
<template>
	<form class="flex flex-col gap-4" data-layout-text-dialog @submit.prevent="close(text.trim())">
		<FormControl
			v-model="text"
			:label="label"
			:placeholder="placeholder"
			:description="description"
			autofocus
		/>
		<div class="flex justify-end gap-2">
			<Button variant="outline" :label="__('Cancel')" @click="close(null)" />
			<Button type="submit" variant="solid" :label="confirmLabel" />
		</div>
	</form>
</template>

<script setup lang="ts">
import { ref } from "vue";
import { Button, FormControl } from "frappe-ui";
import { __ } from "@/i18n";

const props = defineProps<{
	label: string;
	value: string;
	placeholder?: string;
	description?: string;
	confirmLabel: string;
	close: (text: string | null) => void;
}>();

const text = ref(props.value);
</script>
