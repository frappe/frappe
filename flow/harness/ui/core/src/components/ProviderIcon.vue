<template>
	<!-- brand marks are drawn for light backgrounds; in dark mode they sit on a
	     small white tile so monochrome logos stay legible. `bare` drops the tile: the mark
	     at full size, a black one turned white in dark mode -->
	<img
		v-if="source && bare"
		:src="source"
		:width="size"
		:height="size"
		alt=""
		aria-hidden="true"
		class="block flex-none object-contain"
		:class="MONOCHROME.has(id) ? 'dark:invert' : ''"
	/>
	<span
		v-else-if="source"
		class="inline-flex flex-none items-center justify-center rounded-5 dark:bg-white"
		:style="{ width: `${size}px`, height: `${size}px` }"
	>
		<img
			:src="source"
			:width="Math.round(size * 0.74)"
			:height="Math.round(size * 0.74)"
			alt=""
			aria-hidden="true"
			class="block object-contain"
		/>
	</span>
	<span
		v-else
		class="lucide-server flex-none text-ink-gray-6"
		:style="{ width: `${size}px`, height: `${size}px` }"
		aria-hidden="true"
	/>
</template>

<script setup>
import { computed } from "vue"
import anthropic from "@lobehub/icons-static-svg/icons/anthropic.svg"
import cerebras from "@lobehub/icons-static-svg/icons/cerebras-color.svg"
import codex from "@lobehub/icons-static-svg/icons/codex.svg"
import deepseek from "@lobehub/icons-static-svg/icons/deepseek-color.svg"
import gemini from "@lobehub/icons-static-svg/icons/gemini-color.svg"
import groq from "@lobehub/icons-static-svg/icons/groq.svg"
import mistral from "@lobehub/icons-static-svg/icons/mistral-color.svg"
import ollama from "@lobehub/icons-static-svg/icons/ollama.svg"
import openai from "@lobehub/icons-static-svg/icons/openai.svg"
import opencode from "@lobehub/icons-static-svg/icons/opencode.svg"
import openrouter from "@lobehub/icons-static-svg/icons/openrouter-color.svg"
import xai from "@lobehub/icons-static-svg/icons/xai.svg"

const props = defineProps({
	providerId: { type: String, required: true },
	size: { type: Number, default: 20 },
	// custom endpoints have no brand id of their own; the server suggests one
	// from their model prefixes (e.g. "ollama")
	icon: { type: String, default: null },
	bare: { type: Boolean, default: false },
})

const icons = {
	openai,
	anthropic,
	gemini,
	openrouter,
	xai,
	groq,
	deepseek,
	mistral,
	cerebras,
	codex,
	"opencode-go": opencode,
	ollama,
}
// the marks drawn in black, which dark mode turns white
const MONOCHROME = new Set(["anthropic", "openai", "xai", "groq", "codex", "opencode-go", "ollama"])
const id = computed(() => (icons[props.providerId] ? props.providerId : props.icon))
const source = computed(() => icons[id.value] || null)
</script>
