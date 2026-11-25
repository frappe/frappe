<template>
	<component :is="tag" :class="[fontSize, 'transition-colors']">
		{{ text }}
	</component>
</template>

<script setup lang="ts">
import type { TextBlockProps } from "@/runtime/types/studio_components/TextBlock"

withDefaults(defineProps<TextBlockProps>(), {
	tag: "span",
	fontSize: "text-base",
})
</script>
