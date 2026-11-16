<!--
  The Color control in its four states: empty, with a value, read-only, and the
  open picker (v1's swatches and the browser's color dialog).
-->
<template>
	<div class="flex max-w-sm flex-col gap-6 p-6">
		<ColorField
			:field="{ ...field, label: 'Empty' }"
			:modelValue="empty"
			@update:modelValue="(v: string) => (empty = v)"
		/>
		<ColorField
			:field="{ ...field, label: 'With a value' }"
			:modelValue="picked"
			@update:modelValue="(v: string) => (picked = v)"
		/>
		<ColorField
			:field="{ ...field, label: 'Read-only', readOnly: true }"
			modelValue="#268c5c"
		/>
		<div class="flex flex-col gap-1.5">
			<span class="text-sm text-ink-gray-6">Open picker</span>
			<div
				class="w-max rounded-6 bg-surface-elevation-2 shadow-2xl ring-1 ring-black ring-opacity-5"
			>
				<ColorPicker :modelValue="picked" @pick="(v: string) => (picked = v)" />
			</div>
		</div>
		<p class="text-p-sm text-ink-gray-5">Stored: {{ picked || "—" }}</p>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue";
import ColorField from "../ColorField.vue";
import ColorPicker from "../ColorPicker.vue";
import type { FieldMeta } from "../types";

const field: FieldMeta = { fieldname: "color", fieldtype: "Color" };

const empty = ref("");
const picked = ref("#1f8cad");
</script>
