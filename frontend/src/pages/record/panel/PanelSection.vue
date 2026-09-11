<!-- One item of the panel. Header and body are siblings, not a wrapping <section>: a
     sticky header cannot outlive its own containing block. -->
<template>
	<div
		v-if="headerIndex !== null"
		class="group/section sticky flex cursor-pointer select-none items-center gap-1.5 bg-surface-base px-4 after:pointer-events-none after:absolute after:inset-x-0 after:top-[calc(100%+1px)] after:h-2.5 after:bg-gradient-to-b after:from-surface-base after:to-transparent after:content-['']"
		:class="index ? 'border-t border-outline-gray-1' : ''"
		:style="{ top: `${headerIndex * HEIGHT}px`, height: `${HEIGHT}px` }"
		:data-section="name"
		@click="$emit('toggle')"
	>
		<button
			type="button"
			class="flex items-center gap-1 py-1 text-base font-semibold text-ink-gray-8"
			:aria-expanded="open"
			@click.stop="$emit('toggle')"
		>
			{{ label }}
			<span
				class="size-4 text-ink-gray-5"
				:class="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
				aria-hidden="true"
			/>
		</button>
	</div>

	<div
		v-if="headerIndex === null || open"
		class="flex flex-col gap-2.5 px-4 py-3 empty:hidden"
		:class="headerIndex === null && divided ? 'border-t border-outline-gray-1' : ''"
		:data-section="headerIndex === null ? name : undefined"
	>
		<slot>
			<PanelField
				v-for="field in fields"
				:key="field.fieldname"
				:field="field"
				@expand="$emit('expand', $event)"
			/>
		</slot>
	</div>
</template>

<script setup lang="ts">
import type { FieldNode } from "@framework/ui/components/FormLayout/types";
import PanelField from "./PanelField.vue";

// Headers stack, each pinned below the ones before it; a fixed height makes the offset
// knowable without measuring.
const HEIGHT = 42;

defineProps<{
	name: string;
	/** Absent on a built-in, which draws no header and no chevron. */
	label?: string;
	fields: FieldNode[];
	index: number;
	/** Where the header pins, or null for a section that shows no header. */
	headerIndex: number | null;
	/** Whether a headerless body draws a divider above itself. */
	divided?: boolean;
	open: boolean;
}>();

defineEmits<{ toggle: []; expand: [field: FieldNode] }>();
</script>
