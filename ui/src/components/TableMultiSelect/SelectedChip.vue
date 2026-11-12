<template>
	<span
		class="inline-flex max-w-full items-center gap-1 border border-outline-gray-1 bg-surface-base px-1.5 text-sm text-ink-gray-7 transition-colors"
		:class="[
			panel ? 'h-5 rounded-3' : 'h-7 rounded-4',
			removable ? 'hover:border-outline-gray-2 hover:bg-surface-gray-1' : '',
		]"
	>
		<span class="truncate">{{ label }}</span>
		<!-- A row at rest keeps the × as space, so opening it never rewraps the chips. -->
		<span
			v-if="removable !== undefined"
			role="button"
			tabindex="-1"
			:aria-hidden="!removable"
			class="-mr-0.5 inline-flex size-4 shrink-0 items-center justify-center rounded-1 opacity-70 hover:opacity-100"
			:class="removable ? 'cursor-pointer' : 'invisible'"
			@click="onClick"
			@pointerdown="removable && $event.stopPropagation()"
		>
			<span class="lucide-x size-3" />
		</span>
	</span>
</template>

<script setup lang="ts">
const props = withDefaults(
	defineProps<{
		label: string;
		/** The 20px chip of a panel row; else the 28px one of the form. */
		panel?: boolean;
		/** Draws the ×: live when true, held as empty space when false, absent when omitted. */
		removable?: boolean;
	}>(),
	{ removable: undefined }
);
const emit = defineEmits<{ remove: [] }>();

// A held × is not a button: its click goes on to the row, which opens.
function onClick(event: MouseEvent) {
	if (!props.removable) return;
	event.stopPropagation();
	emit("remove");
}
</script>
