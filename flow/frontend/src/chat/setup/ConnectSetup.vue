<template>
	<!-- shown once it knows what to offer, so no row arrives late and pushes the others down -->
	<div
		class="flex w-full flex-col text-left transition-opacity duration-200 ease-out"
		:class="[ready ? 'opacity-100' : 'opacity-0', !list && 'max-w-[360px]']"
	>
		<!-- the first run: the popular ones as rows of one list, its last row opening the rest and a
		     server of one's own in the same list -->
		<div v-if="!picked && !list" class="flex flex-col gap-3">
			<p class="text-base-medium text-ink-gray-8">Choose a provider</p>
			<ul class="divide-y divide-outline-gray-1 overflow-hidden rounded-6 border border-outline-gray-2">
				<li v-for="choice in shown" :key="choice.id">
					<button
						type="button"
						class="flex w-full items-center gap-3 px-3 py-2.5 text-left enabled:hover:bg-surface-gray-1 disabled:cursor-default"
						:disabled="Boolean(busy)"
						@click="choice.run()"
					>
						<span v-if="choice.icon" :class="[choice.icon, 'size-[18px] flex-none text-ink-gray-6']" aria-hidden="true" />
						<ProviderIcon v-else :provider-id="choice.id" :size="18" bare class="flex-none" />
						<span class="min-w-0 flex-1 truncate text-base text-ink-gray-8">
							{{ choice.title }}
							<span class="text-ink-gray-5">{{ busy === choice.id ? "Connecting…" : choice.by }}</span>
						</span>
						<span v-if="busy === choice.id" class="lucide-loader-circle size-4 flex-none animate-spin text-ink-gray-5" aria-hidden="true" />
						<span v-else-if="choice.done" class="lucide-check size-4 flex-none text-ink-green-6" aria-label="Connected" />
						<span v-else-if="choice.id !== 'more'" class="lucide-chevron-right size-4 flex-none text-ink-gray-4" aria-hidden="true" />
					</button>
				</li>
			</ul>
			<ErrorMessage :message="hint" />
		</div>

		<!-- settings: every provider a tile, in one grid, the ones connected already marked -->
		<div v-else-if="!picked" class="flex flex-col gap-4">
			<div class="grid grid-cols-2 gap-2 md:grid-cols-3">
				<button
					v-for="choice in all"
					:key="choice.id"
					type="button"
					class="flex min-w-0 items-center gap-3 rounded-6 border border-outline-gray-2 px-3 py-2.5 text-left enabled:hover:bg-surface-gray-1 disabled:cursor-default"
					:disabled="Boolean(busy) || choice.done"
					@click="choice.run()"
				>
					<span
						v-if="busy === choice.id"
						class="lucide-loader-circle size-[18px] flex-none animate-spin text-ink-gray-5"
						aria-hidden="true"
					/>
					<ProviderIcon v-else :provider-id="choice.id" :size="18" bare class="flex-none" />
					<span class="min-w-0 flex-1 truncate text-base text-ink-gray-8">
						{{ choice.title }}
						<span class="text-ink-gray-5">{{ busy === choice.id ? "Connecting…" : choice.by }}</span>
					</span>
					<span v-if="choice.done" class="lucide-check size-4 flex-none text-ink-green-6" aria-label="Connected" />
				</button>
			</div>
			<ErrorMessage :message="hint" />
			<Button
				class="-ml-2 self-start"
				variant="ghost"
				label="Your own server or gateway"
				icon-left="lucide-server"
				@click="emit('manual')"
			/>
		</div>

		<!-- the picked provider: where its key comes from, and the key -->
		<form v-else class="flex flex-col gap-4" :class="list && 'max-w-[400px]'" @submit.prevent="connect">
			<!-- in settings the page's heading names it -->
			<div v-if="!list" class="flex items-center gap-2.5">
				<ProviderIcon :provider-id="picked.id" :size="18" bare />
				<p class="text-base-medium text-ink-gray-8">Connect {{ picked.name }}</p>
			</div>
			<p class="text-p-base text-ink-gray-5">
				Create a key in the
				<a :href="picked.keys" target="_blank" rel="noopener" :class="LINK">
					{{ picked.console }}<span class="lucide-arrow-up-right ml-0.5 inline-block size-3" aria-hidden="true" />
				</a>
				and paste it here.
			</p>
			<FormControl
				v-model="key"
				type="password"
				label="API key"
				placeholder="Paste the key"
				autocomplete="off"
				autofocus
				:disabled="Boolean(busy)"
			/>
			<p v-if="error" class="-mt-2 flex flex-wrap items-center gap-x-2 text-sm">
				<span class="text-ink-red-5">{{ error.message }}</span>
				<a v-if="error.href" :href="error.href" target="_blank" rel="noopener" :class="LINK">
					{{ error.link }}<span class="lucide-arrow-up-right ml-0.5 inline-block size-3" aria-hidden="true" />
				</a>
			</p>
			<div class="flex items-center gap-2">
				<Button type="submit" variant="solid" label="Connect" :loading="Boolean(busy)" :disabled="!key.trim()" />
				<Button v-if="showBack" variant="ghost" label="Back" :disabled="Boolean(busy)" @click="back" />
			</div>
		</form>
	</div>
</template>

<script setup>
import { computed, onMounted, ref, watch } from "vue";
import { Button, ErrorMessage, FormControl } from "frappe-ui";
import ProviderIcon from "@flow/ui-core/components/ProviderIcon.vue";

import { call } from "../../api/frappe.js";
import { OTHERS, PRODUCTS, detectService, serviceFor } from "./services.js";

// Connecting an AI provider: pick one and paste its key, which the server checks with it before
// saving; no model is added. Ollama running beside the site needs no key. `manual` asks for the
// provider form, for a server or gateway Flow doesn't list. Given a `service`, it starts on that
// one (a new key for it), and Back is `cancel`. A page with a Back of its own passes
// `showBack: false` and calls `back()` from it. Settings pass `list`: every provider, those
// `connected` already marked.
const props = defineProps({
	service: { type: String, default: null },
	showBack: { type: Boolean, default: true },
	list: { type: Boolean, default: false },
	connected: { type: Array, default: () => [] },
});
// `picked` tells a page with its own heading which provider the key is for
// `use`: the first run's pick of a provider connected already, which needs no key again
const emit = defineEmits(["connected", "manual", "cancel", "picked", "use"]);

const picked = ref(serviceFor(props.service));
const key = ref("");
const busy = ref(""); // the provider being checked
const error = ref(null); // why the key was refused, with where to fix it
const hint = ref(""); // why Ollama, which has no key line, didn't connect
const ollama = ref([]); // the models of an Ollama running beside the site
const ready = ref(false); // asked the server what it can offer
watch(picked, (now) => emit("picked", now), { immediate: true });

// a key that names its own provider is connected to that one, whichever was picked
watch(key, (value) => {
	error.value = null;
	const named = detectService(value);
	if (named && named.id !== picked.value?.id) picked.value = named;
});

const OLLAMA = { id: "ollama", name: "Ollama" };
// Ollama is saved under LiteLLM's name for its chat endpoint
const taken = computed(() => new Set(props.connected.map((id) => (id === "ollama_chat" ? "ollama" : id))));
const choice = (service) => ({
	id: service.id,
	title: service.name,
	by: service.maker === service.name ? "" : `by ${service.maker}`,
	done: taken.value.has(service.id),
	run: () => (taken.value.has(service.id) ? emit("use", service) : pick(service)),
});
const ollamaChoice = computed(() =>
	ollama.value.length
		? [
				{
					id: "ollama",
					title: "Ollama",
					by: "on this server",
					done: taken.value.has("ollama"),
					run: () => (taken.value.has("ollama") ? emit("use", OLLAMA) : check(OLLAMA, null)),
				},
			]
		: []
);
const all = computed(() => [...ollamaChoice.value, ...PRODUCTS.map(choice), ...OTHERS.map(choice)]);
// the first run's list: the popular ones, then a row that opens the rest in place
const expanded = ref(false);
const shown = computed(() => {
	const popular = [...ollamaChoice.value, ...PRODUCTS.map(choice)];
	const rest = [
		...OTHERS.map(choice),
		{ id: "server", icon: "lucide-server", title: "Your own server or gateway", by: "", run: () => emit("manual") },
	];
	const more = { id: "more", icon: "lucide-ellipsis", title: "More providers", by: "", run: () => (expanded.value = true) };
	return [...popular, ...(expanded.value ? rest : [more])];
});

function pick(service) {
	picked.value = service;
	error.value = null;
	hint.value = "";
}

// out of the picked provider to the list; from the list, or a provider given, out of setup
function back() {
	if (busy.value) return;
	if (props.service || !picked.value) return emit("cancel");
	picked.value = null;
	key.value = "";
	error.value = null;
}

function connect() {
	if (key.value.trim()) check(picked.value, key.value.trim());
}

// the server asks the provider, saves it when the key works, and says why when it doesn't
async function check(service, apiKey) {
	busy.value = service.id;
	error.value = null;
	hint.value = "";
	try {
		const result = await call("frappe.flow.api.setup.connect", { provider: service.id, api_key: apiKey });
		if (result.ok) return emit("connected", { service });
		error.value = refusal(service, result);
	} catch (failure) {
		error.value = { message: failure.message };
	} finally {
		busy.value = "";
	}
	if (!apiKey && error.value) hint.value = error.value.message;
}

function refusal(service, { reason, message }) {
	if (reason === "wrong_key") return { message, href: service.keys, link: "Create a new key" };
	return { message };
}

onMounted(async () => {
	try {
		ollama.value = (await call("frappe.flow.api.setup.setup_options")).ollama ?? [];
	} catch {
		// the listed providers are offer enough
	}
	ready.value = true;
});
defineExpose({ back });

const LINK =
	"inline-flex items-center text-ink-gray-7 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-outline-gray-6";
</script>
