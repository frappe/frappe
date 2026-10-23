<template>
	<div
		class="flex max-h-[min(500px,72vh)] flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base shadow-[0_1px_2px_rgba(0,0,0,0.06),0_8px_24px_-10px_rgba(0,0,0,0.18)]"
	>
		<div class="flex items-start gap-3 px-3.5 py-2.5">
			<div class="min-w-0 flex-1 text-base leading-snug text-ink-gray-9">{{ title }}</div>
			<span
				v-if="subagent != null"
				class="max-w-[45%] flex-none truncate rounded-full bg-surface-gray-2 px-2 py-0.5 text-2xs font-medium text-ink-gray-6"
			>
				Sub-agent{{ subagent ? `: ${subagent}` : "" }}
			</span>
			<span
				v-if="total > 1"
				class="flex-none rounded-full bg-surface-gray-2 px-2 py-0.5 text-2xs font-medium text-ink-gray-6"
			>
				{{ position }} of {{ total }}
			</span>
		</div>

		<!-- the host's view fills the card body with its own padding, so a table can go edge to edge -->
		<div v-if="presentation.argsComponent" class="overflow-y-auto border-y border-outline-gray-1">
			<component :is="presentation.argsComponent" :arguments="args" />
		</div>
		<pre
			v-else-if="body"
			class="m-0 max-h-[260px] overflow-auto border-y border-outline-gray-1 bg-surface-gray-1 px-3.5 py-2 font-mono text-2xs leading-[1.7] text-ink-gray-6"
		>{{ body }}</pre>
		<div v-else-if="edits" class="max-h-[260px] overflow-auto border-y border-outline-gray-1 bg-surface-gray-1">
			<div v-for="(r, i) in edits" :key="i" :class="i > 0 ? 'border-t border-outline-gray-1' : ''">
				<pre
					class="m-0 grid overflow-auto px-3.5 py-1 font-mono text-2xs leading-[1.7]"
				><span v-for="(line, j) in r.old.split('\n')" :key="'o' + j" class="block bg-surface-red-1 text-ink-red-6">- {{ line }}</span><span v-for="(line, j) in r.new.split('\n')" :key="'n' + j" class="block bg-surface-green-1 text-ink-green-6">+ {{ line }}</span></pre>
			</div>
		</div>

		<div v-if="!asking" class="flex items-center justify-end gap-2 px-3.5 py-2.5">
			<button class="flow-btn-ghost" @click="asking = true">Ask for changes</button>
			<button class="flow-btn-secondary" @click="answer('Deny')">Deny</button>
			<button class="flow-btn-primary" @click="answer('Approve')">Approve</button>
		</div>
		<div v-else class="px-3.5 py-2.5">
			<!-- function ref: the field mounts only while asking, so mount-time focus
			     is exactly "form opened" -->
			<textarea
				:ref="focusAsk"
				v-model="askText"
				rows="2"
				placeholder="Describe what you want instead…"
				class="w-full resize-none rounded-6 border border-outline-gray-2 bg-surface-base px-2.5 py-2 text-xs leading-normal text-ink-gray-9 outline-none focus:border-outline-gray-3 focus:ring-0"
				@keydown="onAskKey"
			/>
			<div class="mt-2 flex items-center gap-2">
				<span class="min-w-0 flex-1 truncate text-2xs text-ink-gray-4">⏎ send · esc cancel</span>
				<button class="flow-btn-ghost" @click="cancelAsk">Cancel</button>
				<button
					class="flow-btn-primary"
					:class="askText.trim() ? '' : 'pointer-events-none opacity-50'"
					@click="sendAsk"
				>
					Send
				</button>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, ref } from "vue"

import { layout } from "../layout.js"

// One gated call, answered here. The composer shows the batch one call at a time,
// and the call's place in it tells the user how many questions follow.
const props = defineProps({
	call: { type: Object, required: true },
	position: { type: Number, default: 1 },
	total: { type: Number, default: 1 },
	// asked by a sub-agent the session runs, named by its description
	subagent: { type: String, default: null },
})
const flow = inject("flow")

const asking = ref(false)
const askText = ref("")

// On a phone the card comes up under a finger that was going somewhere else, or takes the
// place of the call just answered: a tap in its first moment answers nothing.
const shownAt = Date.now()
function answer(text) {
	if (layout.phone && Date.now() - shownAt < 400) return
	flow.answerApproval(props.call.id, text)
}

// a ref fires before its node is in the document, where focus() is a no-op; the tick
// after, the field exists and the typing lands in it
function focusAsk(el) {
	if (el) nextTick(() => el.focus())
}

const args = computed(() => props.call.args ?? props.call.arguments ?? {})

// a host's own tools may name the action better than the server prompt does
const presentation = computed(() => flow.options?.presentTool?.(props.call.name, args.value) ?? {})

const title = computed(() => {
	const a = args.value
	const custom = presentation.value.title
	if (custom != null) return custom
	switch (props.call.name) {
		case "bash":
			return "Run this command?"
		case "edit": {
			const n = a.edits?.length ?? 1
			return `Apply ${n} edit${n === 1 ? "" : "s"} to ${a.path ?? "file"}?`
		}
		case "write":
			return `Write ${a.path ?? "file"}?`
		default:
			return props.call.prompt?.split("\n")[0] ?? `Approve ${props.call.name}?`
	}
})

const edits = computed(() => {
	if (props.call.name !== "edit") return null
	const list = args.value.edits
	if (!Array.isArray(list)) return null
	return list.map((r) => ({ old: r.old ?? "", new: r.new ?? "" }))
})

const body = computed(() => {
	const a = args.value
	const custom = presentation.value.body
	if (custom != null) return custom
	if (props.call.name === "bash") return a.command ?? ""
	if (props.call.name === "write") return a.content ?? ""
	if (props.call.name === "edit") return null
	// generic: server-provided prompt already includes the argument JSON
	const prompt = props.call.prompt ?? ""
	const rest = prompt.split("\n").slice(1).join("\n").trim()
	return rest || JSON.stringify(a, null, 2)
})

function sendAsk() {
	const text = askText.value.trim()
	if (!text) return
	flow.answerApproval(props.call.id, text)
	asking.value = false
	askText.value = ""
}

function cancelAsk() {
	asking.value = false
	askText.value = ""
}

// an IME's Enter and Escape pick or drop a candidate (Safari marks its closing key by keyCode 229)
function onAskKey(e) {
	if (e.isComposing || e.keyCode === 229) return
	if (e.key === "Escape") return cancelAsk()
	if (e.key !== "Enter" || e.shiftKey || e.altKey || e.ctrlKey || e.metaKey) return
	e.preventDefault()
	sendAsk()
}
</script>
