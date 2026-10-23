<!-- The conversation log: every step's JSON beside its role, with the
     provider's usage under the request that reported it. -->
<template>
	<Teleport to="body">
		<div
			v-if="flow.state.transcriptOpen"
			class="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-2 sm:p-6"
			role="dialog"
			aria-modal="true"
			aria-label="Transcript"
			@click.self="close"
		>
			<!-- on a phone the totals scroll away with the steps under a pinned title; wider, only the steps scroll -->
			<section
				class="flex max-h-full w-full max-w-[1100px] flex-col overflow-y-auto rounded-7 border border-outline-gray-2 bg-surface-base shadow-2xl sm:overflow-hidden"
			>
				<header class="sticky top-0 z-10 flex-none bg-surface-base p-4 sm:static sm:px-6 sm:pb-0 sm:pt-5">
					<div class="flex items-start justify-between gap-4">
						<div class="min-w-0">
							<h2 class="text-base font-semibold leading-5 text-ink-gray-9">Transcript</h2>
							<div v-if="title" class="mt-1.5 truncate text-sm text-ink-gray-6">{{ title }}</div>
						</div>
						<button ref="closeEl" class="flow-icon-btn flex-none" title="Close" @click="close">
							<FeatherIcon name="x" class="h-3.5 w-3.5" />
						</button>
					</div>
				</header>
				<div class="flex flex-none flex-wrap gap-2 border-b border-outline-gray-1 px-4 pb-4 sm:mt-4 sm:px-6 sm:pb-5">
					<div
						v-for="stat in stats"
						:key="stat.label"
						class="min-w-[132px] flex-1 rounded-5 border border-outline-gray-1 px-3.5 py-3"
					>
						<div class="text-2xs text-ink-gray-5">{{ stat.label }}</div>
						<div class="mt-2 flex items-baseline gap-1.5">
							<span class="text-sm font-semibold tabular-nums text-ink-gray-9">{{ stat.value }}</span>
							<span v-if="stat.sub" class="truncate text-2xs text-ink-gray-4">{{ stat.sub }}</span>
						</div>
					</div>
				</div>

				<div class="px-4 pb-2 sm:min-h-0 sm:flex-1 sm:overflow-y-auto sm:px-6">
					<div v-if="!rows.length" class="py-10 text-center text-xs text-ink-gray-5">Nothing sent yet.</div>
					<div
						v-for="row in rows"
						:key="row.key"
						class="grid grid-cols-[4.5rem_minmax(0,1fr)] gap-x-4 border-b border-outline-gray-1 py-3.5 last:border-0 sm:grid-cols-[5.5rem_minmax(0,1fr)]"
					>
						<span class="font-mono text-2xs font-medium leading-5 text-ink-gray-5">{{ ROLES[row.kind] }}</span>
						<div class="min-w-0 space-y-2 text-xs leading-5">
							<p v-if="row.body" class="max-h-[280px] overflow-auto whitespace-pre-wrap break-words text-ink-gray-8">{{ row.body }}</p>
							<!-- a tool's call and result, and a request's usage, are labelled -->
							<div v-for="part in PARTS.filter((name) => row[name])" :key="part">
								<div v-if="part !== 'entry'" class="mb-1 font-mono text-2xs text-ink-gray-4">{{ part }}</div>
								<pre
									class="m-0 max-h-[280px] overflow-auto whitespace-pre-wrap break-words rounded-4 bg-surface-gray-1 px-3 py-2 font-mono text-2xs leading-5 text-ink-gray-6"
								>{{ JSON.stringify(row[part], null, 2) }}</pre>
							</div>
						</div>
					</div>
				</div>

			</section>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, ref, watch } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { buildTranscriptRows, formatTokens } from "../transcript.js"

const ROLES = {
	system: "system",
	user: "user",
	assistant: "assistant",
	tool: "tool",
	compaction: "compact",
	error: "error",
}
// the row's raw objects, in the order they show
const PARTS = ["entry", "input", "output", "usage"]

const flow = inject("flow")
const closeEl = ref(null)

const conversation = computed(() => flow.state.conversation)
const title = computed(() => flow.state.session?.title ?? "")
const rows = computed(() => buildTranscriptRows(conversation.value))

const stats = computed(() => {
	const { usage, requests, subagents, contextTokens, contextWindow } = conversation.value
	// the totals count a sub-agent's usage as this session's, so its calls count too
	const calls = Object.values(subagents ?? {}).reduce((n, child) => n + child.requests.length, requests.length)
	const cached = usage.input ? Math.round((usage.cacheRead / usage.input) * 100) : 0
	const stats = [
		{ label: "Tokens", value: formatTokens(usage.input + usage.output), sub: cached ? `${cached}% cached` : "" },
		{ label: "Input", value: formatTokens(usage.input) },
		{ label: "Output", value: formatTokens(usage.output) },
		{ label: "Model calls", value: String(calls) },
	]
	if (contextTokens) {
		stats.push({
			label: "Context",
			value: formatTokens(contextTokens),
			sub: contextWindow ? `of ${formatTokens(contextWindow)}` : "",
		})
	}
	if (usage.cost) stats.push({ label: "Cost", value: `$${usage.cost.toFixed(usage.cost < 1 ? 3 : 2)}` })
	return stats
})

function close() {
	flow.setTranscriptOpen(false)
}

// capture phase: the open dialog owns Escape before the composer's global
// abort listener acts on the same keypress
function onKey(event) {
	if (event.key !== "Escape") return
	event.preventDefault()
	event.stopPropagation()
	close()
}

let returnFocus = null
watch(
	() => flow.state.transcriptOpen,
	(isOpen) => {
		if (isOpen) {
			returnFocus = document.activeElement
			window.addEventListener("keydown", onKey, true)
			nextTick(() => closeEl.value?.focus())
		} else {
			window.removeEventListener("keydown", onKey, true)
			returnFocus?.focus?.()
		}
	},
)
onBeforeUnmount(() => window.removeEventListener("keydown", onKey, true))
</script>
