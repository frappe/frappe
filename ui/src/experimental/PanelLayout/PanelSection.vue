<!-- One collapsible group of panel rows. Header and fields are siblings, not a wrapping
     <section>: a sticky header cannot outlive its own containing block. -->
<template>
	<div
		v-if="headerIndex !== null"
		class="group/section sticky flex cursor-pointer select-none items-center gap-1.5 bg-surface-base px-4 after:pointer-events-none after:absolute after:inset-x-0 after:top-[calc(100%+1px)] after:h-2.5 after:bg-gradient-to-b after:from-surface-base after:to-transparent after:content-['']"
		:class="index ? 'border-t border-outline-gray-1' : ''"
		:style="{ top: `${headerIndex * HEIGHT}px`, height: `${HEIGHT}px` }"
		@click="$emit('toggle')"
	>
		<button
			type="button"
			class="flex items-center gap-1 py-1 text-base font-semibold text-ink-gray-8"
			:aria-expanded="open"
			@click.stop="$emit('toggle')"
		>
			{{ title }}
			<span
				class="size-4 text-ink-gray-5"
				:class="open ? 'lucide-chevron-up' : 'lucide-chevron-down'"
				aria-hidden="true"
			/>
		</button>
		<div class="ml-auto" @click.stop>
			<slot name="header-action" />
		</div>
	</div>

	<div
		v-if="headerIndex === null || open"
		class="flex flex-col gap-2.5 px-4 pb-3 pt-2.5"
		:class="headerIndex === null && index ? 'border-t border-outline-gray-1' : ''"
	>
		<PanelField
			v-for="field in fields"
			:key="field.fieldname"
			:field="field"
			@expand="$emit('expand', $event)"
		/>
	</div>
</template>

<script setup lang="ts">
import PanelField from "./PanelField.vue";
import type { FieldNode, Section } from "../../components/FormLayout/types";

// Headers stack rather than push, so each pins below the ones before it — a fixed
// height is what makes that offset knowable without measuring.
const HEIGHT = 42;

defineProps<{
	section: Section;
	title: string;
	fields: FieldNode[];
	index: number;
	/** Where the header pins, or null for a section that shows no header. */
	headerIndex: number | null;
	open: boolean;
}>();

defineEmits<{ toggle: []; expand: [field: FieldNode] }>();
</script>
