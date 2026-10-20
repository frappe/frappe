<template>
	<PalettePanel
		:title="selected?.name || 'Providers'"
		back
		:query="query"
		:busy="!selected && query !== debouncedQuery"
		:full="loading && !rows.length"
		@close="emit('close')"
		@back="selected ? deselect() : emit('back')"
	>
		<template v-if="!selected" #actions>
			<button
				class="grid h-6 w-6 place-items-center rounded-full text-ink-gray-5 hover:bg-surface-gray-2 hover:text-ink-gray-8"
				title="Refresh providers"
				@click="reload"
			>
				<FeatherIcon name="refresh-cw" class="h-3.5 w-3.5" :class="loading ? 'animate-spin' : ''" />
			</button>
		</template>

		<!-- provider list -->
		<div v-if="!selected" class="flow-palette-list min-h-0 flex-1 overflow-y-auto p-1">
			<button
				v-for="p in filtered"
				:key="p.id"
				data-palette-item
				class="flow-palette-row"
				@click="select(p)"
			>
				<span class="min-w-0 flex-1 truncate">{{ p.name }}</span>
				<span
					v-if="p.configured"
					class="flex items-center gap-1 text-2xs font-medium text-ink-green-7"
				>
					<span class="h-1.5 w-1.5 rounded-full bg-surface-green-7" />
					Connected
				</span>
				<FeatherIcon v-else name="chevron-right" class="flow-palette-hint h-4 w-4 flex-none" />
			</button>
			<LoadingState v-if="loading && !rows.length" class="justify-center px-3 py-7 text-xs text-ink-gray-5" />
			<div
				v-if="!filtered.length && debouncedQuery && !loading"
				class="flow-palette-empty"
			>
				No providers found
			</div>
			<!-- the last row: local runtimes and private gateways; it waits for the list, so the
			     first provider, not it, takes the highlight -->
			<button
				v-if="rows.length || !loading"
				data-palette-item
				class="flow-palette-row"
				@click="select(CUSTOM_OPTION)"
			>
				<FeatherIcon name="plus" class="h-4 w-4 flex-none" />
				<span class="flex-none">Add custom endpoint</span>
				<span class="flow-palette-hint min-w-0 flex-1 truncate">
					Ollama, LM Studio, or any OpenAI-compatible URL
				</span>
				<FeatherIcon name="chevron-right" class="flow-palette-hint h-4 w-4 flex-none" />
			</button>
		</div>

		<!-- provider detail -->
		<div v-else class="min-h-0 flex-1 overflow-y-auto p-4">
			<!-- the custom form repeats name and URL as fields; the header would only spend space -->
			<div v-if="!selected.custom_setup && !selected.custom" class="flex items-center gap-3">
				<span class="flex h-10 w-10 flex-none items-center justify-center">
					<ProviderIcon :provider-id="selected.id" :icon="selected.icon" :size="28" />
				</span>
				<div class="min-w-0">
					<div class="truncate text-sm font-semibold text-ink-gray-9">{{ selected.name }}</div>
					<div class="truncate text-xs text-ink-gray-5">{{ selected.source || "Not connected" }}</div>
				</div>
			</div>

			<!-- custom endpoint setup: adds a new one, or edits the selected one in place -->
			<form v-if="selected.custom_setup || selected.custom" class="flex flex-col gap-3" @submit.prevent="saveCustom">
				<label class="block">
					<span class="mb-1.5 block text-xs font-medium text-ink-gray-7">Name</span>
					<input v-model="customName" :class="FIELD" placeholder="Local Ollama" />
				</label>
				<label class="block">
					<span class="mb-1.5 block text-xs font-medium text-ink-gray-7">Base URL</span>
					<input v-model="customBaseUrl" :class="FIELD" placeholder="http://localhost:11434/v1" />
				</label>
				<label class="block">
					<span class="mb-1.5 block text-xs font-medium text-ink-gray-7">Models</span>
					<textarea
						v-model="customModelIds"
						rows="3"
						:class="[FIELD, 'h-auto resize-none py-2 leading-relaxed']"
						placeholder="ollama/llama3.2&#10;ollama/qwen2.5"
					/>
					<span class="mt-1 block text-2xs leading-4 text-ink-gray-5">
						One per line (or comma separated). Each id needs a prefix, e.g.
						<code class="text-ink-gray-6">ollama/llama3.2</code>.
					</span>
				</label>
				<label class="block">
					<span class="mb-1.5 block text-xs font-medium text-ink-gray-7">
						API key <span class="font-normal text-ink-gray-4">(optional)</span>
					</span>
					<input
						v-model="customApiKey"
						type="password"
						autocomplete="off"
						:class="FIELD"
						:placeholder="editingCustom ? 'Leave empty to keep the saved key' : 'Leave empty for local runtimes'"
					/>
				</label>
				<div class="mt-1 flex items-center gap-2">
					<button
						v-if="editingCustom"
						type="button"
						class="flex h-8 items-center gap-1.5 rounded-5 px-3 text-xs font-medium text-ink-red-6 hover:bg-surface-red-1"
						:disabled="saving"
						@click="disconnect"
					>
						<FeatherIcon name="log-out" class="h-3.5 w-3.5" />
						Disconnect
					</button>
					<button
						type="submit"
						class="flex h-8 items-center gap-1.5 rounded-5 bg-surface-gray-10 px-3 text-xs font-medium text-ink-base hover:opacity-90 disabled:cursor-not-allowed disabled:border disabled:border-outline-gray-2 disabled:bg-surface-gray-1 disabled:text-ink-gray-4 disabled:hover:opacity-100"
						:disabled="!canSaveCustom || saving"
					>
						<FeatherIcon :name="editingCustom ? 'check' : 'plus'" class="h-3.5 w-3.5" />
						{{ editingCustom ? "Save changes" : "Add endpoint" }}
					</button>
				</div>
			</form>

			<div v-else-if="selected.configured" class="mt-5">
				<div
					class="flex items-center gap-2 rounded-5 border border-outline-gray-1 bg-surface-gray-1 px-3 py-2.5 text-xs text-ink-gray-7"
				>
					<FeatherIcon name="check-circle" class="h-4 w-4 text-ink-green-7" />
					Ready to use
				</div>
				<button
					v-if="selected.credential_type"
					class="mt-3 flex h-8 items-center gap-1.5 rounded-5 px-3 text-xs font-medium text-ink-red-6 hover:bg-surface-red-1"
					:disabled="saving"
					@click="disconnect"
				>
					<FeatherIcon name="log-out" class="h-3.5 w-3.5" />
					Disconnect
				</button>
			</div>

			<form v-else-if="selected.auth_methods.includes('api_key')" class="mt-5" @submit.prevent="saveKey">
				<label class="mb-1.5 block text-xs font-medium text-ink-gray-7">API key</label>
				<input
					v-model="apiKey"
					type="password"
					autocomplete="off"
					class="h-9 w-full rounded-5 border border-outline-gray-2 bg-surface-base px-3 text-sm text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:border-outline-gray-4 focus:ring-0"
					placeholder="Paste your API key"
				/>
				<button
					type="submit"
					class="mt-3 flex h-8 items-center gap-1.5 rounded-5 bg-surface-gray-10 px-3 text-xs font-medium text-ink-base hover:opacity-90 disabled:cursor-not-allowed disabled:border disabled:border-outline-gray-2 disabled:bg-surface-gray-1 disabled:text-ink-gray-4 disabled:hover:opacity-100"
					:disabled="!apiKey.trim() || saving"
				>
					<FeatherIcon name="key" class="h-3.5 w-3.5" />
					Save API key
				</button>
			</form>

			<div v-else class="mt-5">
				<button
					v-if="!['pending', 'waiting_manual', 'exchanging', 'connected'].includes(oauthStatus)"
					class="flex h-9 items-center gap-2 rounded-5 bg-surface-gray-10 px-3.5 text-xs font-medium text-ink-base hover:opacity-90 disabled:opacity-50"
					:disabled="saving"
					@click="beginOAuth"
				>
					<FeatherIcon name="external-link" class="h-3.5 w-3.5" />
					Sign in
				</button>
				<div
					v-else-if="oauthStatus !== 'connected'"
					class="flex items-center gap-2 rounded-5 border border-outline-gray-1 bg-surface-gray-1 px-3 py-2.5 text-xs text-ink-gray-7"
				>
					<span class="flow-shimmer font-medium">
						{{ oauthStatus === "exchanging" ? "Finishing sign-in…" : "Waiting for sign-in…" }}
					</span>
				</div>
				<!-- popup blockers eat the window.open after the awaited /start —
				     the link is the reliable, user-gesture path -->
				<a
					v-if="authorizeUrl && ['pending', 'waiting_manual'].includes(oauthStatus)"
					:href="authorizeUrl"
					target="_blank"
					rel="noopener noreferrer"
					class="mt-2 flex w-fit items-center gap-1.5 text-xs text-ink-gray-6 underline hover:text-ink-gray-9"
				>
					<FeatherIcon name="external-link" class="h-3 w-3" />
					Open the sign-in page
				</a>
				<div
					v-if="oauthStatus === 'connected'"
					class="flex items-center gap-2 rounded-5 border border-outline-gray-1 bg-surface-gray-1 px-3 py-2.5 text-xs text-ink-gray-7"
				>
					<FeatherIcon name="check-circle" class="h-4 w-4 text-ink-green-7" />
					Connected
				</div>
				<div v-if="oauthError" class="mt-2 text-xs leading-relaxed text-ink-red-6">
					{{ oauthError }}
				</div>
				<button
					v-if="['pending', 'waiting_manual'].includes(oauthStatus) && !showManual"
					class="mt-3 block text-xs text-ink-gray-5 hover:text-ink-gray-8"
					@click="showManual = true"
				>
					Enter callback URL
				</button>
				<form v-if="showManual" class="mt-3" @submit.prevent="completeOAuth">
					<input
						v-model="callbackUrl"
						class="h-9 w-full rounded-5 border border-outline-gray-2 bg-surface-base px-3 text-xs text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:border-outline-gray-4 focus:ring-0"
						placeholder="http://localhost:1455/auth/callback?..."
					/>
					<button
						type="submit"
						class="mt-2 flex h-8 items-center gap-1.5 rounded-5 border border-outline-gray-2 px-3 text-xs font-medium text-ink-gray-7 hover:bg-surface-gray-1 disabled:opacity-50"
						:disabled="!callbackUrl.trim() || saving"
					>
						Complete sign-in
					</button>
				</form>
			</div>
		</div>
	</PalettePanel>
</template>

<script setup>
import { computed, inject, onBeforeUnmount, ref, toRef } from "vue"
import FeatherIcon from "./FeatherIcon.vue"

import { useDebouncedValue } from "../debounce.js"
import LoadingState from "./LoadingState.vue"
import PalettePanel from "./PalettePanel.vue"
import ProviderIcon from "./ProviderIcon.vue"

const props = defineProps({ query: { type: String, default: "" } }) // the composer's text after its "/"
const emit = defineEmits(["close", "back"])
const flow = inject("flow")

const rows = ref([])
const loading = ref(false)
const selected = ref(null)
const debouncedQuery = useDebouncedValue(toRef(props, "query"), 150)
const apiKey = ref("")
const saving = ref(false)
const oauthStatus = ref("idle")
const oauthError = ref("")
const showManual = ref(false)
const callbackUrl = ref("")
const authorizeUrl = ref("")
let pollTimer = null

const FIELD =
	"h-9 w-full rounded-5 border border-outline-gray-2 bg-surface-base px-3 text-xs text-ink-gray-9 outline-none placeholder:text-ink-gray-4 focus:border-outline-gray-4 focus:ring-0"

// the synthetic row that opens the custom-endpoint form
const CUSTOM_OPTION = {
	id: "__custom__",
	name: "Custom endpoint",
	auth_methods: ["custom"],
	configured: false,
	custom_setup: true,
}

const customName = ref("")
const customBaseUrl = ref("")
const customApiKey = ref("")
const customModelIds = ref("")

// a saved custom row opens the same form prefilled and saves in place
const editingCustom = computed(() => !!selected.value?.custom)

// ids may be newline- or comma-separated; the server dedupes and re-validates
const customModels = computed(() =>
	customModelIds.value
		.split(/[\n,]/)
		.map((m) => m.trim())
		.filter(Boolean),
)
const canSaveCustom = computed(
	() =>
		!!customName.value.trim() &&
		!!customBaseUrl.value.trim() &&
		customModels.value.length > 0 &&
		customModels.value.every((m) => m.includes("/")),
)

async function saveCustom() {
	saving.value = true
	const editing = editingCustom.value
	try {
		const payload = {
			name: customName.value.trim(),
			base_url: customBaseUrl.value.trim(),
			models: customModels.value,
			api_key: customApiKey.value.trim() || null,
		}
		const data = editing
			? await flow.client.updateCustomProvider(selected.value.id, payload)
			: await flow.client.saveCustomProvider(payload)
		flow.notify(`${data.provider.name} ${editing ? "updated" : "added"}`)
		await reload()
		flow.refreshModels()
		// prefill from the response row: it is authoritative even if reload failed
		select(data.provider)
	} catch (error) {
		flow.notify(error.message, "error")
	} finally {
		saving.value = false
	}
}

// only the newest reload lands, so an older answer can't end its loading or replace its list
let reloadRequest = 0
async function reload() {
	const own = ++reloadRequest
	loading.value = true
	try {
		const { providers } = await flow.client.providers()
		if (own !== reloadRequest) return
		rows.value = providers
		// the custom-setup row is synthetic and never in the server's list
		if (selected.value && !selected.value.custom_setup) {
			selected.value = rows.value.find((p) => p.id === selected.value.id) ?? null
		}
	} catch (error) {
		if (own === reloadRequest) flow.notify(error.message, "error")
	} finally {
		if (own === reloadRequest) loading.value = false
	}
}
reload()

const filtered = computed(() => {
	const q = debouncedQuery.value.trim().toLowerCase()
	if (!q) return rows.value
	return rows.value.filter((p) => p.name.toLowerCase().includes(q) || p.id.includes(q))
})

function select(p) {
	stopPolling() // a poll started for another provider must not follow us here
	selected.value = p
	apiKey.value = ""
	oauthStatus.value = "idle"
	oauthError.value = ""
	showManual.value = false
	callbackUrl.value = ""
	authorizeUrl.value = ""
	customName.value = p.custom ? p.name : ""
	customBaseUrl.value = p.custom ? p.source : p.custom_setup ? "http://localhost:11434/v1" : ""
	customApiKey.value = "" // never echoed back; blank means "keep the saved key"
	customModelIds.value = p.custom ? (p.models ?? []).join("\n") : ""
}

function deselect() {
	stopPolling()
	selected.value = null
}

async function saveKey() {
	saving.value = true
	try {
		await flow.client.saveProviderKey(selected.value.id, apiKey.value.trim())
		flow.notify(`${selected.value.name} key saved`)
		apiKey.value = ""
		await reload()
		flow.refreshModels()
	} catch (error) {
		flow.notify(error.message, "error")
	} finally {
		saving.value = false
	}
}

async function disconnect() {
	saving.value = true
	try {
		await flow.client.deleteProvider(selected.value.id)
		await reload()
		flow.refreshModels()
	} catch (error) {
		flow.notify(error.message, "error")
	} finally {
		saving.value = false
	}
}

async function beginOAuth() {
	saving.value = true
	oauthError.value = ""
	try {
		const started = await flow.client.oauthStart(selected.value.id)
		authorizeUrl.value = started.authorize_url
		window.open(started.authorize_url, "_blank", "noopener")
		oauthStatus.value = started.status
		startPolling()
	} catch (error) {
		oauthError.value = error.message
	} finally {
		saving.value = false
	}
}

async function completeOAuth() {
	saving.value = true
	try {
		const status = await flow.client.oauthComplete(selected.value.id, callbackUrl.value.trim())
		applyStatus(status)
	} catch (error) {
		oauthError.value = error.message
	} finally {
		saving.value = false
	}
}

function startPolling() {
	stopPolling()
	const providerId = selected.value.id // pinned: navigation must not retarget the poll
	const poll = (pollTimer = setInterval(async () => {
		try {
			const status = await flow.client.oauthStatus(providerId)
			// a stopped poll's late answer is for a provider no longer shown
			if (poll === pollTimer) applyStatus(status)
		} catch {
			if (poll === pollTimer) stopPolling()
		}
	}, 1500))
}

function applyStatus(status) {
	oauthStatus.value = status.status
	oauthError.value = status.error ?? ""
	if (status.status === "connected") {
		stopPolling()
		reload()
		flow.refreshModels()
	} else if (["error", "expired"].includes(status.status)) {
		stopPolling()
	}
}

function stopPolling() {
	clearInterval(pollTimer)
	pollTimer = null
}

onBeforeUnmount(stopPolling)
</script>
