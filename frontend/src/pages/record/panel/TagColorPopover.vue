<!-- The colour step: the 13 named colours; the tag's colour shows in the header. -->
<template>
	<Popover :open="open" trigger="manual" :side="side" :align="align" @update:open="onOpen">
		<template #trigger><slot /></template>
		<div class="flex w-52 flex-col" data-tag-colors>
			<p
				class="flex items-center gap-2 border-b border-outline-gray-2 px-3 py-2 text-base text-ink-gray-8"
			>
				<span
					class="size-2.5 shrink-0 rounded-full"
					:class="colorClass(TAG_COLOR_NAMES[index])"
					aria-hidden="true"
				/>
				<span class="min-w-0 truncate">{{ tag }}</span>
			</p>
			<div class="flex flex-col p-1">
				<!-- tabindex -1 keeps the popover's autofocus off the first row -->
				<button
					v-for="(name, row) in TAG_COLOR_NAMES"
					:key="name"
					type="button"
					tabindex="-1"
					class="flex h-8 shrink-0 items-center gap-2 rounded-4 px-2 text-base text-ink-gray-7"
					:class="{ 'bg-surface-alpha-gray-2': row === index }"
					@mouseenter="index = row"
					@click="emit('select', name)"
				>
					<span
						class="size-2.5 shrink-0 rounded-full"
						:class="colorClass(name)"
						aria-hidden="true"
					/>
					{{ __(name) }}
				</button>
			</div>
		</div>
	</Popover>
</template>

<script setup lang="ts">
import { ref, watch } from "vue";
import { useEventListener } from "@vueuse/core";
import { Popover } from "frappe-ui";
import { __ } from "@/i18n";
import { colorClass, TAG_COLOR_NAMES } from "@/tagColors";

const props = defineProps<{
	open: boolean;
	tag: string;
	current?: string;
	side: "top" | "right" | "bottom" | "left";
	align: "start" | "center" | "end";
}>();
const emit = defineEmits<{ select: [color: string]; close: [] }>();

const index = ref(0);

watch(
	() => props.open,
	(opened) => {
		if (opened) index.value = Math.max(TAG_COLOR_NAMES.indexOf(props.current ?? ""), 0);
	}
);

function onOpen(opened: boolean) {
	if (!opened) emit("close");
}

// Capture phase: nothing here takes typing, so a letter key would reach the shortcuts and close the step.
useEventListener(
	document,
	"keydown",
	(event: KeyboardEvent) => {
		if (!props.open) return;
		if (event.key === "ArrowDown" || event.key === "ArrowUp") {
			event.preventDefault();
			const step = event.key === "ArrowDown" ? 1 : -1;
			index.value = (index.value + step + TAG_COLOR_NAMES.length) % TAG_COLOR_NAMES.length;
		} else if (event.key === "Enter") {
			event.preventDefault();
			emit("select", TAG_COLOR_NAMES[index.value]);
		}
		const modified = event.ctrlKey || event.metaKey || event.altKey;
		if (!modified && event.key !== "Escape" && event.key !== "Tab") event.stopPropagation();
	},
	{ capture: true }
);
</script>
