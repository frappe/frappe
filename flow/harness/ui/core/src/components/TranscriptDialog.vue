<!-- The conversation log: each step as it reads beside its role, its JSON a click away,
     with the provider's usage under the request that reported it. -->
<template>
	<!-- into the host's root where it has one, as frappe-ui's dialogs go: an island's styles live there.
	     Its overlay and card take frappe-ui's Dialog colours -->
	<Teleport :to="portalTarget ?? 'body'">
		<div
			v-if="flow.state.transcriptOpen"
			class="fixed inset-0 z-50 flex items-center justify-center bg-black-overlay-200 p-2 dark:bg-black-overlay-700 sm:p-6"
			role="dialog"
			aria-modal="true"
			aria-label="Transcript"
			@click.self="close"
		>
			<!-- on a phone the totals scroll away with the steps under a pinned title; wider, only the steps scroll -->
			<section
				class="flex max-h-full w-full max-w-[1100px] flex-col overflow-y-auto rounded-7 bg-surface-elevation-1 shadow-xl sm:overflow-hidden"
			>
				<header class="sticky top-0 z-10 flex-none bg-surface-elevation-1 p-4 sm:static sm:px-6 sm:pb-0 sm:pt-5">
					<div class="flex items-center gap-2">
						<h2 class="min-w-0 flex-1 text-md font-semibold text-ink-gray-9">Transcript</h2>
						<!-- for an issue or another chat: the steps as they show, as JSON -->
						<template v-if="rows.length">
							<CopyButton :text="json" title="Copy JSON" :class="HEAD_BTN">
								<span class="max-sm:hidden">Copy JSON</span>
							</CopyButton>
							<button :class="HEAD_BTN" title="Download JSON" @click="download">
								<span class="lucide-download size-3.5" aria-hidden="true" />
								<span class="max-sm:hidden">Download</span>
							</button>
						</template>
						<button ref="closeEl" class="flow-icon-btn flex-none" title="Close" @click="close">
							<span class="lucide-x size-3.5" aria-hidden="true" />
						</button>
					</div>
					<div v-if="title" class="mt-1 truncate text-base text-ink-gray-6">{{ title }}</div>
				</header>
				<div class="flex flex-none flex-wrap gap-2 border-b border-outline-gray-1 px-4 pb-4 sm:mt-4 sm:px-6 sm:pb-5">
					<div
						v-for="stat in stats"
						:key="stat.label"
						class="min-w-[132px] flex-1 rounded-5 border border-outline-gray-1 px-3.5 py-3"
					>
						<div class="text-xs text-ink-gray-5">{{ stat.label }}</div>
						<div class="mt-2 flex items-baseline gap-1.5">
							<span class="text-base font-semibold tabular-nums text-ink-gray-9">{{ stat.value }}</span>
							<span v-if="stat.sub" class="truncate text-xs text-ink-gray-4">{{ stat.sub }}</span>
						</div>
					</div>
				</div>

				<div class="px-4 pb-2 sm:min-h-0 sm:flex-1 sm:overflow-y-auto sm:px-6">
					<div v-if="!rows.length" class="py-10 text-center text-sm text-ink-gray-5">Nothing sent yet.</div>
					<template v-for="(row, index) in rows" :key="row.key">
						<!-- each user message opens a turn -->
						<!-- the role, the first line and the JSON button share one baseline -->
						<div
							class="flex items-baseline gap-4 border-outline-gray-1 py-3"
							:class="index ? 'border-t' : ''"
						>
							<span
								class="w-[4.5rem] flex-none font-mono text-xs leading-6 sm:w-[5.5rem]"
								:class="row.kind === 'error' ? 'text-ink-red-4' : 'text-ink-gray-5'"
								>{{ ROLES[row.kind] }}</span
							>
							<div class="min-w-0 flex-1 space-y-2 text-sm leading-6 text-ink-gray-8">
								<template v-if="row.kind === 'system'">
									<button
										v-if="prompt"
										class="-ml-1.5 flex h-6 items-center gap-1 rounded-4 px-1.5 text-ink-gray-8 hover:bg-surface-gray-2"
										:aria-expanded="opened.has(row.key)"
										@click="toggle(row.key)"
									>
										<span
											class="lucide-chevron-right size-3.5 transition-transform"
											:class="{ 'rotate-90': opened.has(row.key) }"
											aria-hidden="true"
										/>
										System prompt
									</button>
									<p v-else class="text-ink-gray-5">{{ row.body }}</p>
									<pre v-if="prompt && opened.has(row.key)" :class="PRE">{{ prompt }}</pre>
								</template>
								<template v-else-if="row.kind === 'user'">
									<p class="whitespace-pre-wrap break-words">{{ userText(row.entry) }}</p>
									<p v-if="userAttachments(row.entry).length" class="text-ink-gray-5">
										Attached: {{ userAttachments(row.entry).map((file) => file.name).join(", ") }}
									</p>
								</template>
								<template v-else-if="row.kind === 'assistant'">
									<template v-for="(block, index) in row.entry.content" :key="index">
										<p v-if="block.type === 'text'" class="whitespace-pre-wrap break-words">{{ block.text }}</p>
										<!-- a provider may send thinking with no text: nothing to read -->
										<p
											v-else-if="block.type === 'thinking' && (block.redacted || block.thinking?.trim())"
											class="whitespace-pre-wrap break-words text-ink-gray-5"
										>{{ block.redacted ? "Thinking, not shown by the provider." : block.thinking }}</p>
									</template>
									<p v-if="onlyCalls(row.entry)" class="text-ink-gray-5">
										Called {{ row.entry.content.map((block) => block.name).join(", ") }}
									</p>
									<p v-if="row.entry.error_message" class="whitespace-pre-wrap break-words text-ink-red-4">{{ row.entry.error_message }}</p>
								</template>
								<!-- the tool by its name, its arguments and result folded under it -->
								<template v-else-if="row.kind === 'tool'">
									<p>
										<code class="rounded-4 bg-surface-gray-2 px-1.5 py-0.5 font-mono text-xs text-ink-gray-8">{{ row.input.name }}</code>
									</p>
									<div v-for="fold in folds(row)" :key="fold.key">
										<button
											class="-ml-1.5 flex h-6 items-center gap-1 rounded-4 px-1.5 hover:bg-surface-gray-2"
											:class="fold.error ? 'text-ink-red-4' : 'text-ink-gray-7'"
											:aria-expanded="opened.has(fold.key)"
											@click="toggle(fold.key)"
										>
											<span
												class="lucide-chevron-right size-3.5 transition-transform"
												:class="{ 'rotate-90': opened.has(fold.key) }"
												aria-hidden="true"
											/>
											{{ fold.label }}
										</button>
										<pre v-if="opened.has(fold.key)" class="mt-1.5" :class="PRE">{{ fold.text }}</pre>
									</div>
								</template>
								<template v-else-if="row.kind === 'compaction'">
									<p class="text-ink-gray-5">Summary of the chat so far</p>
									<p class="whitespace-pre-wrap break-words">{{ row.entry.summary }}</p>
								</template>
								<template v-else-if="row.kind === 'error'">
									<p class="whitespace-pre-wrap break-words text-ink-red-4">{{ row.entry.message }}</p>
									<p v-if="row.entry.detail" class="whitespace-pre-wrap break-words text-ink-gray-5">{{ row.entry.detail }}</p>
								</template>
								<p v-if="row.usage" class="tabular-nums text-ink-gray-5">{{ usageLine(row.usage) }}</p>
								<template v-if="opened.has(`${row.key}:json`)">
									<div v-for="part in PARTS.filter((name) => row[name])" :key="part">
										<div v-if="part !== 'entry'" class="mb-1 font-mono text-xs text-ink-gray-5">{{ part }}</div>
										<pre :class="PRE">{{ JSON.stringify(row[part], null, 2) }}</pre>
									</div>
								</template>
							</div>
							<!-- a user message's time before its JSON button -->
							<span v-if="row.ts" class="flex-none text-xs tabular-nums text-ink-gray-5">{{ formatTime(row.ts) }}</span>
							<button
								v-if="row.kind !== 'system'"
								class="flex h-6 flex-none items-center rounded-4 px-1.5 font-mono text-xs"
								:class="
									opened.has(`${row.key}:json`)
										? 'bg-surface-gray-3 text-ink-gray-8'
										: 'text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8'
								"
								:aria-expanded="opened.has(`${row.key}:json`)"
								@click="toggle(`${row.key}:json`)"
							>
								JSON
							</button>
						</div>
					</template>
				</div>
			</section>
		</div>
	</Teleport>
</template>

<script setup>
import { computed, inject, nextTick, onBeforeUnmount, reactive, ref, watch } from "vue"
import { usePortalTarget } from "frappe-ui/src/composables/usePortalTarget"

import { buildTranscriptRows, formatCost, formatTime, formatTokens, userAttachments, userText } from "../transcript.js"
import CopyButton from "./CopyButton.vue"

const portalTarget = usePortalTarget()

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
const HEAD_BTN =
	"flex h-7 flex-none items-center gap-1.5 rounded-5 bg-surface-gray-2 px-2 text-sm text-ink-gray-8 hover:bg-surface-gray-3"
const PRE =
	"m-0 max-h-[360px] overflow-auto whitespace-pre-wrap break-words rounded-4 border border-outline-gray-1 bg-surface-gray-1 px-3 py-2 font-mono text-xs leading-5 text-ink-gray-7"

const flow = inject("flow")
const closeEl = ref(null)

const conversation = computed(() => flow.state.conversation)
const title = computed(() => flow.state.session?.title ?? "")
const rows = computed(() => buildTranscriptRows(conversation.value))

// the real system prompt where the host sends it (a System Manager's), else the stand-in
const prompt = ref(null)
watch(
	() => flow.state.transcriptOpen && flow.state.sessionId,
	async (sid) => {
		prompt.value = null
		const text = sid ? await flow.systemPrompt?.(sid) : null
		if (flow.state.transcriptOpen && flow.state.sessionId === sid) prompt.value = text ?? null
	},
	{ immediate: true },
)

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
	if (usage.cost) stats.push({ label: "Cost", value: formatCost(usage.cost) })
	return stats
})

// the system prompt, the folds and the JSON shown, by row key
const opened = reactive(new Set())
function toggle(key) {
	if (!opened.delete(key)) opened.add(key)
}

// a tool's arguments and result; a result that is JSON reads as JSON
function folds(row) {
	const folds = [{ key: `${row.key}:args`, label: "Arguments", text: JSON.stringify(row.input.arguments ?? {}, null, 2) }]
	if (row.output) {
		const error = !!row.output.is_error
		folds.push({ key: `${row.key}:result`, label: error ? "Error" : "Result", text: pretty(row.output.content), error })
	}
	return folds
}

function pretty(text) {
	try {
		return JSON.stringify(JSON.parse(text), null, 2)
	} catch {
		return text
	}
}

const onlyCalls = (entry) => entry.content.length > 0 && entry.content.every((block) => block.type === "tool_call")

function usageLine(usage) {
	const parts = [`${formatTokens(usage.input_tokens)} in`, `${formatTokens(usage.output_tokens)} out`]
	if (usage.cache_read_tokens) parts.push(`${formatTokens(usage.cache_read_tokens)} cached`)
	if (usage.cost) parts.push(formatCost(usage.cost))
	return parts.join(" · ")
}

const json = computed(() =>
	JSON.stringify(
		{
			session: flow.state.sessionId,
			title: title.value,
			rows: rows.value.map(({ key, ...row }) => (row.kind === "system" && prompt.value ? { kind: row.kind, prompt: prompt.value } : row)),
		},
		null,
		2,
	),
)

function download() {
	const url = URL.createObjectURL(new Blob([json.value], { type: "application/json" }))
	const link = Object.assign(document.createElement("a"), { href: url, download: `transcript-${flow.state.sessionId ?? "chat"}.json` })
	link.click()
	setTimeout(() => URL.revokeObjectURL(url))
}

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

// the focused element, inside a shadow root where Flow runs in one
function deepActive() {
	let active = document.activeElement
	while (active?.shadowRoot?.activeElement) active = active.shadowRoot.activeElement
	return active
}

let returnFocus = null
watch(
	() => flow.state.transcriptOpen,
	(isOpen) => {
		if (isOpen) {
			returnFocus = deepActive()
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
