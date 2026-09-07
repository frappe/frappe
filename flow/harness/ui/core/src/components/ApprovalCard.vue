<template>
	<div class="flex flex-col gap-3">
		<div
			v-for="{ call, presentation } in presentedCalls"
			:key="call.id"
			class="overflow-hidden rounded-6 border border-outline-gray-2 bg-surface-base shadow-sm"
		>
			<div class="px-3.5 py-2.5">
				<div class="text-base leading-snug text-ink-gray-9">{{ title(call, presentation) }}</div>
			</div>

			<div v-if="presentation.argsComponent" class="border-y border-outline-gray-1 px-3.5 py-2">
				<component :is="presentation.argsComponent" :arguments="args(call)" />
			</div>
			<pre
				v-else-if="body(call, presentation)"
				class="m-0 max-h-[260px] overflow-auto border-y border-outline-gray-1 bg-surface-gray-1 px-3.5 py-2 font-mono text-2xs leading-[1.7] text-ink-gray-6"
			>{{ body(call, presentation) }}</pre>
			<div v-else-if="edits(call)" class="border-y border-outline-gray-1 bg-surface-gray-1">
				<div v-for="(r, i) in edits(call)" :key="i" :class="i > 0 ? 'border-t border-outline-gray-1' : ''">
					<pre
						class="m-0 overflow-auto px-3.5 py-1 font-mono text-2xs leading-[1.7]"
					><span v-for="(line, j) in r.old.split('\n')" :key="'o' + j" class="block bg-surface-red-1 text-ink-red-6">- {{ line }}</span><span v-for="(line, j) in r.new.split('\n')" :key="'n' + j" class="block bg-surface-green-1 text-ink-green-6">+ {{ line }}</span></pre>
				</div>
			</div>

			<div v-if="answered(call)" class="flex items-center gap-2 px-3.5 py-2.5">
				<span class="text-xs text-ink-gray-5">Answered: {{ answered(call) }}</span>
			</div>
			<div v-else-if="asking !== call.id" class="flex items-center justify-end gap-2 px-3.5 py-2.5">
				<button class="flow-btn-ghost" @click="asking = call.id">Ask for changes</button>
				<button class="flow-btn-secondary" @click="flow.answerApproval(call.id, 'Deny')">Deny</button>
				<button class="flow-btn-primary" @click="flow.answerApproval(call.id, 'Approve')">Approve</button>
			</div>
			<div v-else class="px-3.5 py-2.5">
				<!-- function ref: the field mounts only when this call is being asked
				     about, so mount-time focus is exactly "form opened" -->
				<textarea
					:ref="(el) => el?.focus()"
					v-model="askText"
					rows="2"
					placeholder="Describe what you want instead…"
					class="w-full resize-none rounded-6 border border-outline-gray-2 bg-surface-base px-2.5 py-2 text-xs leading-normal text-ink-gray-9 outline-none focus:border-outline-gray-3 focus:ring-0"
					@keydown.enter.exact.prevent="sendAsk(call)"
					@keydown.esc="cancelAsk"
				/>
				<div class="mt-2 flex items-center gap-2">
					<span class="min-w-0 flex-1 truncate text-2xs text-ink-gray-4">⏎ send · esc cancel</span>
					<button class="flow-btn-ghost" @click="cancelAsk">Cancel</button>
					<button
						class="flow-btn-primary"
						:class="askText.trim() ? '' : 'pointer-events-none opacity-50'"
						@click="sendAsk(call)"
					>
						Send
					</button>
				</div>
			</div>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue"

const props = defineProps({
	calls: { type: Array, required: true },
	seq: { type: Number, required: true },
})
const flow = inject("flow")

const asking = ref(null)
const askText = ref("")

function answered(call) {
	return flow.state.conversation.pendingApproval?.answers[call.id] ?? null
}

function args(call) {
	return call.args ?? call.arguments ?? {}
}

// a host's own tools may name the action better than the server prompt does
const presentedCalls = computed(() =>
	props.calls.map((call) => ({
		call,
		presentation: flow.options?.presentTool?.(call.name, args(call)) ?? {},
	})),
)

function title(call, presentation) {
	const a = args(call)
	const custom = presentation.title
	if (custom != null) return custom
	switch (call.name) {
		case "bash":
			return "Run this command?"
		case "edit": {
			const n = a.edits?.length ?? 1
			return `Apply ${n} edit${n === 1 ? "" : "s"} to ${a.path ?? "file"}?`
		}
		case "write":
			return `Write ${a.path ?? "file"}?`
		default:
			return call.prompt?.split("\n")[0] ?? `Approve ${call.name}?`
	}
}

function edits(call) {
	if (call.name !== "edit") return null
	const list = args(call).edits
	if (!Array.isArray(list)) return null
	return list.map((r) => ({ old: r.old ?? "", new: r.new ?? "" }))
}

function body(call, presentation) {
	const a = args(call)
	const custom = presentation.body
	if (custom != null) return custom
	if (call.name === "bash") return a.command ?? ""
	if (call.name === "write") return a.content ?? ""
	if (call.name === "edit") return null
	// generic: server-provided prompt already includes the argument JSON
	const prompt = call.prompt ?? ""
	const rest = prompt.split("\n").slice(1).join("\n").trim()
	return rest || JSON.stringify(a, null, 2)
}

function sendAsk(call) {
	const text = askText.value.trim()
	if (!text) return
	flow.answerApproval(call.id, text)
	asking.value = null
	askText.value = ""
}

function cancelAsk() {
	asking.value = null
	askText.value = ""
}
</script>
