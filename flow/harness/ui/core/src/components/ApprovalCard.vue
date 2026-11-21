<template>
	<div
		class="flex max-h-[min(500px,calc(72vh/var(--flow-zoom,1)))] flex-col overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base"
	>
		<div class="flex items-start gap-3 px-3.5 py-2.5">
			<div class="min-w-0 flex-1">
				<div class="text-base-medium leading-snug text-ink-gray-8">{{ title }}</div>
				<div v-if="asked.reason" class="mt-0.5 text-sm leading-snug text-ink-gray-5">
					{{ __("Not auto-approved: {0}", [asked.reason]) }}
				</div>
			</div>
			<span
				v-if="subagent != null"
				class="max-w-[45%] flex-none truncate rounded-full bg-surface-gray-2 px-2 py-0.5 text-xs-medium text-ink-gray-6"
			>
				{{ subagent ? __("Sub-agent: {0}", [subagent]) : __("Sub-agent") }}
			</span>
			<span
				v-if="total > 1"
				class="flex-none rounded-full bg-surface-gray-2 px-2 py-0.5 text-xs-medium text-ink-gray-6"
			>
				{{ __("{0} of {1}", [position, total]) }}
			</span>
		</div>

		<!-- the host's view fills the card body with its own padding, so a table can go edge to edge -->
		<div v-if="presentation.argsComponent" class="overflow-y-auto border-y border-outline-gray-1">
			<component
				:is="presentation.argsComponent"
				:arguments="args"
				v-bind="takesCall ? { call: { ...call, prompt: asked.prompt } } : {}"
			/>
		</div>
		<pre
			v-else-if="body"
			class="m-0 max-h-[260px] overflow-auto border-y border-outline-gray-1 bg-surface-gray-1 px-3.5 py-2 font-mono text-xs leading-[1.7] text-ink-gray-6"
		>{{ body }}</pre>
		<div v-else-if="edits" class="max-h-[260px] overflow-auto border-y border-outline-gray-1 bg-surface-gray-1">
			<div v-for="(r, i) in edits" :key="i" :class="i > 0 ? 'border-t border-outline-gray-1' : ''">
				<pre
					class="m-0 grid overflow-auto px-3.5 py-1 font-mono text-xs leading-[1.7]"
				><span v-for="(line, j) in r.old.split('\n')" :key="'o' + j" class="block bg-surface-red-1 text-ink-red-6">- {{ line }}</span><span v-for="(line, j) in r.new.split('\n')" :key="'n' + j" class="block bg-surface-green-1 text-ink-green-6">+ {{ line }}</span></pre>
			</div>
		</div>

		<!-- a host view that answers the card itself brings its own buttons -->
		<div v-if="!asking && !presentation.ownAnswers" class="flex items-center justify-end gap-2 px-3.5 py-2.5">
			<Button ref="askButton" variant="ghost" :label="__('Ask for changes')" @click="asking = true" />
			<Button variant="subtle" :label="__('Deny')" @click="answer('Deny')" />
			<Button variant="solid" :label="__('Approve')" @click="answer('Approve')" />
		</div>
		<div v-else-if="asking" class="px-3.5 py-2.5">
			<!-- function ref: the field mounts only while asking, so mount-time focus
			     is exactly "form opened" -->
			<Textarea
				:ref="focusAsk"
				v-model="askText"
				variant="outline"
				:rows="2"
				:placeholder="__('Describe what you want instead…')"
				class="resize-none"
				@keydown="onAskKey"
			/>
			<div class="mt-2 flex items-center gap-2">
				<span class="min-w-0 flex-1 truncate text-xs text-ink-gray-4">{{ __("⏎ send · esc cancel") }}</span>
				<Button variant="ghost" :label="__('Cancel')" @click="cancelAsk" />
				<Button variant="solid" :label="__('Send')" :disabled="!askText.trim()" @click="sendAsk" />
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, nextTick, ref } from "vue"
import { Button } from "frappe-ui/src/components/Button"
import { Textarea } from "frappe-ui/src/components/Textarea"

import { layout } from "../layout.js"
import { __ } from "../translate.js"

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
const askButton = ref(null)
function focusAsk(el) {
	if (el) nextTick(() => el.focus())
}

const args = computed(() => props.call.args ?? props.call.arguments ?? {})

// In auto mode the server ends the prompt with why its reviewer held the call. The header
// says it, so the body and a host's view get the prompt without it.
const REASON = "\n\nNot auto-approved: "
const asked = computed(() => {
	const prompt = props.call.prompt ?? ""
	const at = prompt.lastIndexOf(REASON)
	if (at < 0) return { prompt, reason: "" }
	return { prompt: prompt.slice(0, at), reason: prompt.slice(at + REASON.length).trim() }
})

// a host's own tools may name the action better than the server prompt does
const presentation = computed(() => flow.options?.presentTool?.(props.call.name, args.value) ?? {})

// a view that declares a `call` prop reads the call itself, such as the server's prompt
const takesCall = computed(() => {
	const declared = presentation.value.argsComponent?.props
	return Array.isArray(declared) ? declared.includes("call") : !!declared?.call
})

const title = computed(() => {
	const a = args.value
	const custom = presentation.value.title
	if (custom != null) return custom
	const path = a.path ?? __("file")
	switch (props.call.name) {
		case "bash":
			return a.description || __("Run this command?")
		case "edit": {
			const n = a.edits?.length ?? 1
			return n === 1 ? __("Apply 1 edit to {0}?", [path]) : __("Apply {0} edits to {1}?", [n, path])
		}
		case "write":
			return __("Write {0}?", [path])
		default:
			return asked.value.prompt.split("\n")[0] || __("Approve {0}?", [props.call.name])
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
	const rest = asked.value.prompt.split("\n").slice(1).join("\n").trim()
	return rest || JSON.stringify(a, null, 2)
})

function sendAsk() {
	const text = askText.value.trim()
	if (!text) return
	flow.answerApproval(props.call.id, text)
	asking.value = false
	askText.value = ""
}

// the keyboard goes back to the button that opened the field
function cancelAsk() {
	asking.value = false
	askText.value = ""
	nextTick(() => askButton.value?.$el?.focus())
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
