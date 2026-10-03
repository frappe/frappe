<template>
	<Popover v-model:open="open" side="left" align="start">
		<template #trigger>
			<slot />
		</template>
		<div class="flex w-52 flex-col">
			<p
				class="flex items-center gap-2 border-b border-outline-gray-2 px-3 py-2 text-base text-ink-gray-8"
			>
				<span
					class="size-2.5 shrink-0 rounded-full"
					:class="TAG_COLORS[TAG_COLOR_NAMES[colorIndex]]"
				/>
				<span class="min-w-0 truncate">{{ tag }}</span>
			</p>
			<div class="flex flex-col p-1">
				<!-- tabindex -1 keeps the popover's autofocus off the first row -->
				<button
					v-for="(name, index) in TAG_COLOR_NAMES"
					:key="name"
					tabindex="-1"
					class="flex h-8 shrink-0 items-center gap-2 rounded-4 px-2 text-base text-ink-gray-7"
					:class="{ 'bg-surface-alpha-gray-2': index === colorIndex }"
					@mouseenter="colorIndex = index"
					@click="$emit('select', name)"
				>
					<span class="size-2.5 shrink-0 rounded-full" :class="TAG_COLORS[name]" />
					{{ name }}
				</button>
			</div>
		</div>
	</Popover>
</template>

<script setup lang="ts">
import { TAG_COLOR_NAMES, TAG_COLORS } from "./colors";
import { useEventListener } from "@vueuse/core";
import { Popover } from "frappe-ui";
import { ref, watch } from "vue";

defineProps<{ tag: string }>();
const emit = defineEmits<{ select: [color: string] }>();
const open = defineModel<boolean>("open", { required: true });

const colorIndex = ref(0);

function handleKeydown(event: KeyboardEvent) {
	const count = TAG_COLOR_NAMES.length;
	if (event.key === "ArrowDown" || event.key === "ArrowUp") {
		event.preventDefault();
		const step = event.key === "ArrowDown" ? 1 : -1;
		colorIndex.value = (colorIndex.value + step + count) % count;
	} else if (event.key === "Enter") {
		event.preventDefault();
		emit("select", TAG_COLOR_NAMES[colorIndex.value]);
	}
}

// capture phase: must pre-empt reka's handlers and useShortcut's listener
useEventListener(
	document,
	"keydown",
	(event: KeyboardEvent) => {
		if (!open.value) return;
		handleKeydown(event);
		// no input absorbs keys here, so single-key shortcuts (a, t, p, ...) would
		// fire and close the popover; Escape/Tab stay with reka
		if (event.key !== "Escape" && event.key !== "Tab") {
			event.stopPropagation();
		}
	},
	{ capture: true }
);

watch(open, () => (colorIndex.value = 0));
</script>
