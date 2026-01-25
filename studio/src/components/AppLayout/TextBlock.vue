<template>
	<component :is="tag" :class="[fontSize, 'transition-colors']">
		{{ text }}
	</component>
</template>

<script setup lang="ts">
import type { TextBlockProps } from "@/types/studio_components/TextBlock"

withDefaults(defineProps<TextBlockProps>(), {
	tag: "span",
	text: "Text Block",
	fontSize: "text-base",
})
</script>
