<!-- One item of the panel. Header and body are siblings, not a wrapping <section>: a
     sticky header cannot outlive its own containing block. -->
<template>
	<div
		v-if="headerIndex !== null"
		ref="header"
		class="group/section sticky z-[1] flex cursor-pointer select-none items-center gap-1.5 bg-surface-base px-4 after:pointer-events-none after:absolute after:inset-x-0 after:top-[calc(100%+1px)] after:h-2.5 after:bg-gradient-to-b after:from-surface-base after:to-transparent after:content-['']"
		:class="[
			index ? 'border-t border-outline-gray-1' : '',
			covering ? 'after:opacity-100' : 'after:opacity-0',
		]"
		:style="{ top: `${pinTop + headerIndex * HEIGHT}px`, height: `${HEIGHT}px` }"
		:data-section="name"
		@click="$emit('toggle')"
	>
		<button
			type="button"
			class="-mx-1.5 flex items-center gap-1 rounded-4 px-1.5 py-1 text-base font-semibold text-ink-gray-8 focus-visible:bg-surface-gray-2 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-inset focus-visible:ring-outline-gray-3"
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
		<div
			v-if="$slots.actions"
			class="ml-auto flex cursor-default items-center gap-1"
			@click.stop
		>
			<slot name="actions" />
		</div>
	</div>

	<div
		v-if="headerIndex === null || open"
		ref="body"
		class="flex flex-col gap-2.5 px-4 empty:hidden"
		:class="[
			headerIndex === null ? 'py-3' : 'pt-1 pb-3',
			headerIndex === null && divided ? 'border-t border-outline-gray-1' : '',
		]"
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
import { nextTick, onBeforeUnmount, onMounted, ref, watch } from "vue";
import type { FieldNode } from "@framework/ui/FormLayout/types";
import PanelField from "./PanelField.vue";
import { scrollParent } from "./scrollParent";

// Headers stack, each pinned below the ones before it; a fixed height makes the offset
// knowable without measuring.
const HEIGHT = 42;

const props = defineProps<{
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
	/** The height of the pinned block above, which every header pins below. */
	pinTop: number;
}>();

// The fade under a pinned header shows only while rows scroll beneath it; drawn always, it
// greys the top of the first row's fill.
const header = ref<HTMLElement | null>(null);
const body = ref<HTMLElement | null>(null);
const covering = ref(false);
let scroller: HTMLElement | null = null;

function measure() {
	if (!header.value || !body.value) return (covering.value = false);
	covering.value =
		body.value.getBoundingClientRect().top < header.value.getBoundingClientRect().bottom;
}

onMounted(() => {
	scroller = scrollParent(header.value);
	scroller?.addEventListener("scroll", measure, { passive: true });
	measure();
});
onBeforeUnmount(() => scroller?.removeEventListener("scroll", measure));
watch(
	() => [props.open, props.fields.length],
	() => nextTick(measure)
);

defineEmits<{ toggle: []; expand: [field: FieldNode] }>();
</script>
