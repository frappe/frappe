<!-- A Phone column's cell: the number, and the apps' field actions at its end (a call button). -->
<template>
	<div class="flex min-w-0 items-center gap-2">
		<span class="truncate text-base text-ink-gray-8">{{ value }}</span>
		<span
			data-slot="phone-cell-actions"
			:class="[
				'flex shrink-0 items-center',
				SHOW_ON_ROW_HOVER &&
					'opacity-0 focus-within:opacity-100 [[data-slot=list-row]:hover_&]:opacity-100',
			]"
			@click.capture.prevent
		>
			<FieldActionButtons :field="field" :value="value" />
		</span>
	</div>
</template>

<script setup lang="ts">
import { FieldActionButtons } from "@framework/ui/fields";
import type { FieldMeta } from "@framework/ui/fields/types";

// The button is always visible; true shows it only on row hover or focus.
const SHOW_ON_ROW_HOVER = false;

defineProps<{ field: FieldMeta; value: string }>();
</script>
