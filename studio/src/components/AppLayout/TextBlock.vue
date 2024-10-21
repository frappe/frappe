<template>
	<component :is="tag" :class="[fontSize, fontWeight, lineHeight, textColor, 'transition-colors']">
		{{ text }}
	</component>
</template>

<script setup lang="ts">
type FontSize =
	| "text-xs"
	| "text-sm"
	| "text-base"
	| "text-lg"
	| "text-xl"
	| "text-2xl"
	| "text-3xl"
	| "text-4xl"
	| "text-5xl"
type FontWeight = "font-normal" | "font-medium" | "font-semibold" | "font-bold"
type LineHeight =
	| "leading-none"
	| "leading-tight"
	| "leading-snug"
	| "leading-normal"
	| "leading-relaxed"
	| "leading-loose"
type TextColor =
	| "text-gray-900"
	| "text-gray-800"
	| "text-gray-700"
	| "text-gray-600"
	| "text-gray-500"
	| "text-gray-400"

interface Props {
	tag?: string
	fontSize?: FontSize
	fontWeight?: FontWeight
	lineHeight?: LineHeight
	textColor?: TextColor
	text?: string
}

const props = withDefaults(defineProps<Props>(), {
	tag: "span",
	fontSize: "text-base",
	fontWeight: "font-normal",
	lineHeight: "leading-normal",
	textColor: "text-gray-900",
	text: "This is a text block",
})
</script>
