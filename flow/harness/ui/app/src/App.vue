<template>
	<FlowChat v-if="store" :store="store" class="h-full" />

	<div v-else class="flex h-full items-center justify-center bg-surface-white">
		<form
			class="flex w-[380px] flex-col gap-3 rounded-lg border border-outline-gray-2 bg-surface-white p-5 shadow-sm"
			@submit.prevent="connect"
		>
			<div>
				<div class="text-lg font-medium text-ink-gray-9">Connect to flow</div>
				<div class="mt-1 text-sm text-ink-gray-5">Point this UI at a running Flow daemon.</div>
			</div>
			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-ink-gray-7">Daemon URL</span>
				<input
					v-model="baseUrl"
					placeholder="same origin (dev proxy)"
					class="h-8 rounded-md border border-outline-gray-2 bg-surface-white px-2.5 text-sm text-ink-gray-9 outline-none focus:border-outline-gray-3 focus:ring-0"
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-ink-gray-7">Auth token</span>
				<input
					v-model="token"
					type="password"
					placeholder="Leave empty unless the daemon requires one"
					class="h-8 rounded-md border border-outline-gray-2 bg-surface-white px-2.5 text-sm text-ink-gray-9 outline-none focus:border-outline-gray-3 focus:ring-0"
				/>
			</label>
			<div v-if="error" class="rounded-md bg-surface-red-1 px-2.5 py-1.5 text-xs text-ink-red-3">
				{{ error }}
			</div>
			<button
				type="submit"
				class="h-8 rounded-md bg-surface-gray-7 text-sm font-medium text-ink-white hover:opacity-90"
				:disabled="checking"
			>
				{{ checking ? "Connecting…" : "Connect" }}
			</button>
		</form>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { DaemonClient, FlowChat, createFlowStore } from "@flow/ui-core"

const CONNECTION_KEY = "flow.ui.connection"

const store = ref(null)
const baseUrl = ref("")
const token = ref("")
const error = ref("")
const checking = ref(false)

async function tryConnect(config, { silent = false } = {}) {
	checking.value = true
	error.value = ""
	const client = new DaemonClient(config)
	try {
		await client.health()
		localStorage.setItem(CONNECTION_KEY, JSON.stringify(config))
		store.value = createFlowStore(client)
	} catch (err) {
		if (!silent) error.value = err?.message ?? "Could not reach the daemon."
	} finally {
		checking.value = false
	}
}

function connect() {
	tryConnect({ baseUrl: baseUrl.value.trim(), token: token.value.trim() })
}

onMounted(() => {
	let saved = null
	try {
		saved = JSON.parse(localStorage.getItem(CONNECTION_KEY))
	} catch {
		// ignore
	}
	if (saved) {
		baseUrl.value = saved.baseUrl ?? ""
		token.value = saved.token ?? ""
	}
	tryConnect(saved ?? { baseUrl: "", token: "" }, { silent: true })
})
</script>
