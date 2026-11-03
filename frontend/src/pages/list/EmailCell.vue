<!-- An Email column's cell: the shell's email button before the address, which opens the composer floating. -->
<template>
	<div class="flex min-w-0 items-center gap-2">
		<span
			data-slot="email-cell-actions"
			class="flex shrink-0 items-center empty:hidden"
			@click.capture.prevent
		>
			<FieldActionButtons :field="field" :value="value" :record="record" />
		</span>
		<span class="truncate text-base text-ink-gray-8">{{ value }}</span>
	</div>
</template>

<script setup lang="ts">
import { computed } from "vue";
import { FieldActionButtons } from "@framework/ui/fields";
import type { FieldMeta } from "@framework/ui/fields/types";

const props = defineProps<{ field: FieldMeta; value: string; doctype: string; name: string }>();

const record = computed(() => ({
	doctype: props.doctype,
	name: props.name,
	surface: "list" as const,
}));
</script>
