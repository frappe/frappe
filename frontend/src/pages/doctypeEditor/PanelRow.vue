<!-- A label-left row of the field panel, as frappe/crm#3419's PanelRow. `box` wraps a ghost control
     the way desk's FieldBox does. -->
<template>
	<div class="grid grid-cols-[130px_1fr] items-start gap-2">
		<span class="h-7 truncate text-base leading-7 text-ink-gray-5" :title="label">{{
			label
		}}</span>
		<div class="min-w-0">
			<div
				v-if="box"
				class="min-h-7 w-full min-w-0 rounded-4 focus-within:bg-surface-gray-2 focus-within:ring-1 focus-within:ring-inset focus-within:ring-outline-gray-3 hover:bg-surface-gray-2"
			>
				<slot />
			</div>
			<slot v-else />
		</div>
	</div>
</template>

<script setup lang="ts">
withDefaults(defineProps<{ label: string; box?: boolean }>(), { box: true });
</script>
