<template>
	<span
		v-if="hex"
		data-slot="swatch"
		class="inline-block size-3.5 shrink-0 rounded-full border border-outline-gray-2 align-[-2px]"
		:style="{ backgroundColor: hex }"
		aria-hidden="true"
	/>
</template>

<script setup lang="ts">
// Draws nothing unless the field is a Color holding a hex, so a host can place it beside any value.
import { computed } from "vue";
import { normalizeHex } from "./colorHex";
import type { FieldMeta } from "./types";

const props = defineProps<{ field: FieldMeta; value: unknown }>();

const hex = computed(() =>
	props.field.fieldtype === "Color" ? normalizeHex(String(props.value ?? "")) : null
);
</script>
