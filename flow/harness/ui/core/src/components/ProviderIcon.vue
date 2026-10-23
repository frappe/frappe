<template>
	<!-- brand marks are drawn for light backgrounds; in dark mode they sit on a
	     small white tile so monochrome logos stay legible -->
	<span
		v-if="source"
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
	<FeatherIcon
		v-else
		name="server"
		:style="{ width: `${size}px`, height: `${size}px` }"
		class="flex-none text-ink-gray-6"
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
import FeatherIcon from "./FeatherIcon.vue"

const props = defineProps({
	providerId: { type: String, required: true },
	size: { type: Number, default: 20 },
	// custom endpoints have no brand id of their own; the server suggests one
	// from their model prefixes (e.g. "ollama")
	icon: { type: String, default: null },
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
const source = computed(() => icons[props.providerId] || icons[props.icon] || null)
</script>
