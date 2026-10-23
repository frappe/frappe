<template>
	<FlowChat v-if="store" :store="store" class="h-full" />

	<!-- the saved connection is being tried: no form until it fails -->
	<div v-else-if="starting" class="flex h-full items-center justify-center bg-surface-base">
		<LoadingState class="text-sm text-ink-gray-5" />
	</div>

	<div v-else class="flex h-full items-center justify-center bg-surface-base">
		<form
			class="flex w-[380px] flex-col gap-3 rounded-6 border border-outline-gray-2 bg-surface-base p-5 shadow-sm"
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
					class="h-8 rounded-5 border border-outline-gray-2 bg-surface-base px-2.5 text-sm text-ink-gray-9 outline-none focus:border-outline-gray-3 focus:ring-0"
				/>
			</label>
			<label class="flex flex-col gap-1">
				<span class="text-xs font-medium text-ink-gray-7">Auth token</span>
				<input
					v-model="token"
					type="password"
					placeholder="Leave empty unless the daemon requires one"
					class="h-8 rounded-5 border border-outline-gray-2 bg-surface-base px-2.5 text-sm text-ink-gray-9 outline-none focus:border-outline-gray-3 focus:ring-0"
				/>
			</label>
			<div v-if="error" class="rounded-5 bg-surface-red-1 px-2.5 py-1.5 text-xs text-ink-red-6">
				{{ error }}
			</div>
			<button
				type="submit"
				class="h-8 rounded-5 bg-surface-gray-10 text-sm font-medium text-ink-base hover:opacity-90"
				:disabled="checking"
			>
				{{ checking ? "Connecting…" : "Connect" }}
			</button>
		</form>
	</div>
</template>

<script setup>
import { onMounted, ref } from "vue"
import { useColorScheme } from "frappe-ui/src/composables/useColorScheme"
import { DaemonClient, FlowChat, LoadingState, createFlowStore } from "@flow/ui-core"

const CONNECTION_KEY = "flow.ui.connection"
// past this, a slow or stuck daemon gets the form back while the check goes on
const STARTUP_WAIT_MS = 3000

const store = ref(null)
const baseUrl = ref("")
const token = ref("")
const error = ref("")
const checking = ref(false)
const starting = ref(true)
let attempt = 0 // the newest attempt wins; an older one's late answer is dropped

async function tryConnect(config, { silent = false } = {}) {
	const own = ++attempt
	// the silent startup check never locks the form, so a stuck daemon can be replaced
	if (!silent) checking.value = true
	error.value = ""
	const client = new DaemonClient(config)
	try {
		// /healthz answers without a token; this checks the token too
		await client.sessions()
		if (own !== attempt) return
		localStorage.setItem(CONNECTION_KEY, JSON.stringify(config))
		// the daemon keeps the theme with the other settings
		store.value = createFlowStore(client, { colorScheme: useColorScheme() })
	} catch (err) {
		if (own !== attempt) return
		// a refused token shows even on the silent check: only the form can fix it
		if (err?.status === 401) error.value = "The daemon refused the auth token."
		else if (!silent) error.value = err?.message ?? "Could not reach the daemon."
	} finally {
		if (own === attempt) checking.value = false
	}
}

function connect() {
	tryConnect({ baseUrl: baseUrl.value.trim(), token: token.value.trim() })
}

onMounted(async () => {
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
	const showForm = setTimeout(() => (starting.value = false), STARTUP_WAIT_MS)
	await tryConnect(saved ?? { baseUrl: "", token: "" }, { silent: true })
	clearTimeout(showForm)
	starting.value = false
})
</script>
