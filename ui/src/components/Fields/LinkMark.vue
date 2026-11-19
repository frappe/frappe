<template>
	<span
		v-if="source?.kind === 'color' && dot"
		data-slot="link-mark"
		class="inline-block size-2 shrink-0 rounded-full"
		:class="dot.class"
		:style="dot.style"
		aria-hidden="true"
	/>
	<Avatar
		v-else-if="source?.kind === 'image' && (value || text)"
		data-slot="link-mark"
		size="xs"
		:image="value ?? undefined"
		:label="text ?? ''"
		class="shrink-0"
	/>
</template>

<script setup lang="ts">
// The mark before a Link value, from its target's `color` or `image_field`; nothing for no source, an empty colour or an empty Link value.
import { Avatar } from "frappe-ui";
import { computed } from "vue";
import { normalizeHex } from "./colorHex";
import type { LinkMarkSource } from "./types";

const props = defineProps<{
	source?: LinkMarkSource;
	value?: string | null;
	/** The shown title, whose initials stand in for an empty image. */
	text?: string | null;
}>();

// Literal class names, so Tailwind finds them; `bg-current` paints the dot in the ink colour.
const INK: Record<string, string> = {
	black: "text-ink-gray-9",
	gray: "text-ink-gray-6",
	blue: "text-ink-blue-6",
	green: "text-ink-green-7",
	red: "text-ink-red-6",
	pink: "text-ink-pink-6",
	orange: "text-ink-orange-6",
	amber: "text-ink-amber-6",
	yellow: "text-ink-yellow-6",
	cyan: "text-ink-cyan-6",
	teal: "text-ink-teal-6",
	violet: "text-ink-violet-6",
	purple: "text-ink-purple-6",
};

const dot = computed(() => {
	const value = props.value?.trim();
	if (!value) return null;
	if (INK[value]) return { class: ["bg-current", INK[value]], style: undefined };
	const hex = normalizeHex(value);
	return hex ? { class: [], style: { backgroundColor: hex } } : null;
});
</script>
