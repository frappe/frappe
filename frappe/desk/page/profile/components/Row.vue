<script setup>
// One row of a Group, as Gameplan's More menu draws it: an icon column, a divider above
// every row but the first, the label, an optional value and a chevron.
defineProps({
	icon: { type: String, default: "" },
	label: { type: String, required: true },
	value: { type: String, default: "" },
	divider: { type: Boolean, default: false },
	chevron: { type: Boolean, default: true },
});
defineEmits(["click"]);
</script>

<template>
	<button
		type="button"
		class="block w-full text-left transition active:bg-surface-gray-2"
		@click="$emit('click', $event)"
	>
		<!-- the flex layout is on this inner wrapper, not the button: iOS Safari wraps a
		     button's children in an anonymous box and top-aligns a flex button's rows -->
		<span class="flex min-h-14 w-full items-stretch">
			<span class="flex w-14 shrink-0 items-center justify-center py-3">
				<span :class="[icon, 'size-5 text-ink-gray-8']" aria-hidden="true" />
			</span>
			<span class="relative flex min-w-0 flex-1 items-center gap-3 py-3 pr-4">
				<span
					v-if="divider"
					class="pointer-events-none absolute left-0 right-4 top-0 border-t"
					aria-hidden="true"
				/>
				<span class="min-w-0 flex-1 truncate text-lg text-ink-gray-9">{{ label }}</span>
				<span v-if="value" class="max-w-[50%] shrink-0 truncate text-md text-ink-gray-5">
					{{ value }}
				</span>
				<span
					v-if="chevron"
					class="size-4 shrink-0 text-ink-gray-4 lucide-chevron-right"
				/>
			</span>
		</span>
	</button>
</template>
