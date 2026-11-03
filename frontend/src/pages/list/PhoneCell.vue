<!-- A Phone column's cell: the number, and the apps' field actions at its end (a call button). -->
<template>
	<div class="flex min-w-0 items-center gap-2">
		<span class="truncate text-base text-ink-gray-8">{{ value }}</span>
		<span
			data-slot="phone-cell-actions"
			class="flex shrink-0 items-center"
			@click.capture.prevent
		>
			<FieldActionButtons :field="field" :value="value" />
		</span>
	</div>
</template>

<script setup lang="ts">
import { FieldActionButtons } from "@framework/ui/fields";
import type { FieldMeta } from "@framework/ui/fields/types";

defineProps<{ field: FieldMeta; value: string }>();
</script>
