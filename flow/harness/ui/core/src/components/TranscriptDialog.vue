<!-- The conversation log: each step as it reads beside its role, its JSON a click away,
     with the provider's usage under the request that reported it. -->
<template>
	<!-- frappe-ui's Dialog portals where its host keeps overlays (inside an island's shadow root),
	     and brings the overlay, Escape, the focus trap and focus return -->
	<Dialog :open="flow.state.transcriptOpen" size="7xl" @update:open="(open) => open || close()">
		<template #title>
			<div class="flex flex-wrap items-start gap-x-4 gap-y-3 pr-8">
				<div class="min-w-0 flex-1">
					<h2 class="text-2xl-semibold leading-6 text-ink-gray-8">Transcript</h2>
					<div v-if="title" class="mt-1.5 truncate text-base text-ink-gray-6">{{ title }}</div>
				</div>
				<!-- for an issue or another chat: the steps as they show, as JSON -->
				<div v-if="rows.length" class="flex flex-none gap-2">
					<CopyButton :text="json" title="Copy JSON" variant="subtle" size="sm">Copy JSON</CopyButton>
					<Button variant="subtle" size="sm" icon-left="lucide-download" label="Download .json" @click="download" />
				</div>
			</div>
		</template>
		<div class="-mt-2 border-b border-outline-gray-1 pb-5">
			<div class="flex flex-wrap gap-2">
				<div
					v-for="stat in stats"
					:key="stat.label"
					class="min-w-[132px] flex-1 rounded-5 border border-outline-gray-1 px-3.5 py-3"
				>
					<div class="text-xs text-ink-gray-5">{{ stat.label }}</div>
					<div class="mt-2 flex items-baseline gap-1.5">
						<span class="text-base-semibold tabular-nums text-ink-gray-9">{{ stat.value }}</span>
						<span v-if="stat.sub" class="truncate text-xs text-ink-gray-4">{{ stat.sub }}</span>
					</div>
				</div>
			</div>
			<!-- the totals count the title and suggestions calls, which have no row -->
			<p v-if="background" class="mt-3 text-sm text-ink-gray-5">{{ background }}</p>
		</div>

		<div v-if="!rows.length" class="py-10 text-center text-sm text-ink-gray-5">Nothing sent yet.</div>
		<!-- read as the Flow Session form reads: text as text, a tool by its name, JSON on demand -->
		<div
			v-for="row in rows"
			:key="row.key"
			class="grid grid-cols-[minmax(0,1fr)_auto] items-start gap-x-4 gap-y-1 border-b border-outline-gray-1 py-3.5 last:border-0 sm:grid-cols-[5.5rem_minmax(0,1fr)_auto]"
		>
			<!-- each user message opens a turn -->
			<div v-if="turns[row.key]" class="col-span-full mb-2 flex items-baseline gap-3 text-sm-medium text-ink-gray-6">
				<span class="flex-none">Turn {{ turns[row.key] }}</span>
				<span v-if="row.ts" class="flex-none font-normal text-ink-gray-5">{{ formatTime(row.ts) }}</span>
			</div>
			<span
				class="pt-1 text-xs-medium uppercase tracking-wide"
				:class="row.kind === 'error' ? 'text-ink-red-4' : row.kind === 'user' ? 'text-ink-gray-8' : 'text-ink-gray-5'"
				>{{ ROLES[row.kind] }}</span
			>
			<Button
				v-if="row.kind !== 'system'"
				variant="ghost"
				size="sm"
				label="Raw JSON"
				:class="turns[row.key] ? 'row-start-2' : 'row-start-1'"
				class="col-start-2 sm:col-start-3"
				:aria-expanded="opened.has(`${row.key}:raw`)"
				@click="toggle(`${row.key}:raw`)"
			/>
			<div class="col-span-2 min-w-0 space-y-2 text-base leading-6 text-ink-gray-8 sm:col-span-1 sm:col-start-2"
				:class="turns[row.key] ? 'sm:row-start-2' : 'sm:row-start-1'">
				<p v-if="row.body" class="whitespace-pre-wrap break-words">{{ row.body }}</p>
				<template v-else-if="row.kind === 'user'">
					<p class="whitespace-pre-wrap break-words">{{ userText(row.entry) }}</p>
					<p v-if="userAttachments(row.entry).length" class="text-sm text-ink-gray-5">
						Attached: {{ userAttachments(row.entry).map((file) => file.name).join(", ") }}
					</p>
				</template>
				<template v-else-if="row.kind === 'assistant'">
					<template v-for="(block, index) in row.entry.content" :key="index">
						<p v-if="block.type === 'text'" class="whitespace-pre-wrap break-words">{{ block.text }}</p>
						<p v-else-if="block.type === 'thinking'" class="whitespace-pre-wrap break-words text-ink-gray-5">
							{{ block.redacted ? "Thinking, not shown by the provider." : block.thinking }}
						</p>
					</template>
					<p v-if="!row.entry.content.some((block) => block.type !== 'tool_call')" class="text-sm text-ink-gray-5">
						Calls {{ row.entry.content.map((block) => block.name).join(", ") }}
					</p>
					<p v-if="row.entry.error_message" class="whitespace-pre-wrap break-words text-ink-red-4">{{ row.entry.error_message }}</p>
				</template>
				<template v-else-if="row.kind === 'tool'">
					<code class="inline-block rounded-4 bg-surface-gray-2 px-1.5 py-0.5 font-mono text-sm-medium text-ink-gray-8">{{
						row.input.name
					}}</code>
					<div v-for="fold in folds(row)" :key="fold.key">
						<button
							type="button"
							class="flex items-center gap-1 rounded text-sm"
							:class="fold.error ? 'text-ink-red-4' : 'text-ink-gray-6 hover:text-ink-gray-8'"
							:aria-expanded="opened.has(fold.key)"
							@click="toggle(fold.key)"
						>
							<span
								class="lucide-chevron-right size-3.5 flex-none transition-transform"
								:class="{ 'rotate-90': opened.has(fold.key) }"
								aria-hidden="true"
							/>
							{{ fold.label }}
						</button>
						<pre
							v-if="opened.has(fold.key)"
							class="mt-1.5 overflow-auto whitespace-pre-wrap break-words rounded-4 border bg-surface-gray-1 px-3 py-2 font-mono text-xs leading-5 text-ink-gray-7 sm:max-h-[360px]"
							:class="fold.error ? 'border-outline-red-2' : 'border-outline-gray-1'"
						>{{ fold.text }}</pre>
					</div>
					<p v-if="!row.output" class="text-sm text-ink-gray-5">No result</p>
				</template>
				<template v-else-if="row.kind === 'compaction'">
					<p class="text-sm text-ink-gray-5">Summary of the chat so far</p>
					<p class="whitespace-pre-wrap break-words">{{ row.entry.summary }}</p>
				</template>
				<template v-else-if="row.kind === 'error'">
					<p class="whitespace-pre-wrap break-words text-ink-red-4">{{ row.entry.message }}</p>
					<p v-if="row.entry.detail" class="whitespace-pre-wrap break-words text-sm text-ink-gray-5">{{ row.entry.detail }}</p>
				</template>
				<p v-if="row.usage" class="text-sm tabular-nums text-ink-gray-5">{{ usageLine(row.usage) }}</p>
				<pre
					v-if="opened.has(`${row.key}:raw`)"
					class="overflow-auto whitespace-pre-wrap break-words rounded-4 border bg-surface-gray-1 px-3 py-2 font-mono text-xs leading-5 text-ink-gray-7 sm:max-h-[360px]"
					:class="row.kind === 'error' ? 'border-outline-red-2' : 'border-outline-gray-1'"
				>{{ rawJson(row) }}</pre>
			</div>
		</div>
	</Dialog>
</template>

<script setup>
import { computed, inject, reactive } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Dialog } from "frappe-ui/src/components/Dialog"

import { buildTranscriptRows, formatCost, formatTime, formatTokens, userAttachments, userText } from "../transcript.js"
import CopyButton from "./CopyButton.vue"

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
	if (usage.cost) stats.push({ label: "Cost", value: formatCost(usage.cost) })
	return stats
})

const turns = computed(() => {
	const turns = {}
	for (const row of rows.value.filter((row) => row.kind === "user")) turns[row.key] = Object.keys(turns).length + 1
	return turns
})

// the folds and raw JSON shown, by row key
const opened = reactive(new Set())
function toggle(key) {
	if (!opened.delete(key)) opened.add(key)
}

// a tool's arguments and result, folded; a result that is JSON reads as JSON
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

function usageLine(usage) {
	const parts = [`${formatTokens(usage.input_tokens)} in`, `${formatTokens(usage.output_tokens)} out`]
	if (usage.cache_read_tokens) parts.push(`${formatTokens(usage.cache_read_tokens)} cached`)
	if (usage.cost) parts.push(formatCost(usage.cost))
	return parts.join(" · ")
}

function rawJson(row) {
	const parts = PARTS.filter((name) => row[name])
	const raw = parts.length === 1 ? row[parts[0]] : Object.fromEntries(parts.map((name) => [name, row[name]]))
	return JSON.stringify(raw, null, 2)
}

const PURPOSES = { title: "title", replies: "suggestions" }
const background = computed(() => {
	const calls = (conversation.value.requests ?? []).filter((usage) => usage.purpose)
	if (!calls.length) return ""
	const names = [...new Set(calls.map((usage) => PURPOSES[usage.purpose] ?? usage.purpose))].join(", ")
	const tokens = calls.reduce((sum, usage) => sum + (usage.input_tokens ?? 0) + (usage.output_tokens ?? 0), 0)
	const noun = calls.length === 1 ? "call" : "calls"
	return `Includes ${calls.length} background ${noun} (${names}): ${formatTokens(tokens)} tokens`
})

const json = computed(() =>
	JSON.stringify({ session: flow.state.sessionId, title: title.value, rows: rows.value.map(({ key, ...row }) => row) }, null, 2),
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
</script>
