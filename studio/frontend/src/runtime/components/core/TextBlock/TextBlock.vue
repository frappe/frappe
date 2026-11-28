<template>
	<component :is="tag" :class="[fontSize, 'transition-colors']">
		{{ text }}
	</component>
</template>

<script setup lang="ts">
import type { TextBlockProps } from "./types"

withDefaults(defineProps<TextBlockProps>(), {
	tag: "span",
	fontSize: "text-base",
})
</script>
