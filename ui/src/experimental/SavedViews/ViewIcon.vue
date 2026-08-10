<template>
	<span
		v-if="isEmoji"
		class="inline-flex size-4 items-center justify-center text-base leading-none"
	>{{ icon }}</span>
	<IconGlyph v-else :name="name" fallback="list" class="size-4 text-ink-gray-6" />
</template>

<script setup lang="ts">
import { computed } from "vue";
import { IconGlyph, isCustomIconName } from "../IconPicker";

const props = defineProps<{ icon?: string | null }>();

const name = computed(() =>
	isCustomIconName(props.icon)
		? (props.icon as string)
		: (props.icon ?? "").replace(/^lucide-/, "") || "list"
);

const isEmoji = computed(
	() => !isCustomIconName(props.icon) && !/^[a-z0-9-]+$/.test(name.value)
);
</script>
