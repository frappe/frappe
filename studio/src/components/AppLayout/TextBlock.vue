<template>
	<component :is="tag" :class="[fontSize, fontWeight, lineHeight, textColor, 'transition-colors']">
		{{ text }}
	</component>
</template>

<script setup lang="ts">
import type { TextBlockProps } from "@/types/studio_components/TextBlock"

withDefaults(defineProps<TextBlockProps>(), {
	tag: "span",
	fontSize: "text-base",
	fontWeight: "font-normal",
	lineHeight: "leading-normal",
	textColor: "text-gray-900",
	text: "Text Block",
})
</script>
