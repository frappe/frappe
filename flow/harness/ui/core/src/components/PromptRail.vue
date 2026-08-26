<template>
	<nav
		ref="rail"
		class="absolute right-1 top-1/2 z-10 max-h-[72%] -translate-y-1/2"
		aria-label="Go to prompt"
		@mouseleave="hovered = null"
	>
		<div ref="list" class="flow-prompt-rail flex max-h-full flex-col overflow-y-auto py-1">
			<button
				v-for="prompt in prompts"
				:key="prompt.key"
				class="group flex h-2.5 w-6 flex-none items-center justify-end"
				:aria-label="prompt.text"
				:aria-current="prompt.key === activeKey || undefined"
				@mouseenter="onHover(prompt, $event)"
				@focus="onHover(prompt, $event)"
				@blur="hovered = null"
				@click="$emit('select', prompt.key)"
			>
				<!-- ink-* exists only as a text color in the preset; bg needs the raw var -->
				<span
					class="h-0.5 w-3 rounded-full transition-all group-hover:w-5"
					:class="
						prompt.key === activeKey
							? 'bg-[--ink-gray-9]'
							: 'bg-surface-gray-4 group-hover:bg-[--ink-gray-5]'
					"
				/>
			</button>
		</div>
		<div
			v-if="hovered"
			class="pointer-events-none absolute right-full mr-1.5 w-max max-w-[300px] -translate-y-1/2 rounded-lg border border-outline-gray-2 bg-surface-white px-3 py-2 shadow-md"
			:style="{ top: hovered.y + 'px' }"
		>
			<p class="line-clamp-6 whitespace-pre-wrap break-words text-xs leading-relaxed text-ink-gray-8">
				{{ hovered.text }}
			</p>
		</div>
	</nav>
</template>

<script setup>
import { nextTick, ref, watch } from "vue"

const props = defineProps({
	prompts: { type: Array, required: true }, // [{key, text}]
	activeKey: { type: String, default: null },
})
defineEmits(["select"])

const rail = ref(null)
const list = ref(null)
const hovered = ref(null)

function onHover(prompt, event) {
	const bar = event.currentTarget.getBoundingClientRect()
	const origin = rail.value.getBoundingClientRect()
	hovered.value = { text: prompt.text, y: bar.top + bar.height / 2 - origin.top }
}

// When the rail itself overflows, keep the active bar in view. Manual scrollTop
// math, not scrollIntoView: Chromium runs one smooth scroll at a time, so a
// scrollIntoView here would cancel the message list's in-flight jump.
watch(
	() => props.activeKey,
	() =>
		void nextTick(() => {
			const el = list.value
			const bar = el?.querySelector('[aria-current="true"]')
			if (!bar || el.scrollHeight <= el.clientHeight) return
			const top = bar.offsetTop - el.offsetTop
			if (top < el.scrollTop) el.scrollTop = top
			else if (top + bar.offsetHeight > el.scrollTop + el.clientHeight)
				el.scrollTop = top + bar.offsetHeight - el.clientHeight
		}),
)
</script>
