<template>
	<!-- the first run inside the chat itself: a greeting, then the one thing missing and who can
	     add it. Hung from the top, not centred: what changes below (a picked provider, an error)
	     never moves the greeting -->
	<div class="flex w-full flex-1 flex-col items-center gap-8 self-stretch pb-10 pt-[min(18vh,160px)]">
		<div class="flex flex-col items-center gap-4 text-center">
			<BrandMark line :size="28" />
			<div class="flex flex-col gap-1.5">
				<h1 class="text-2xl-semibold text-ink-gray-9">{{ greeting }}</h1>
				<p class="max-w-sm text-pretty text-p-base text-ink-gray-5">{{ subline }}</p>
			</div>
		</div>
		<template v-if="canConnect">
			<!-- connected, a model is picked to start with; nothing is added on its own -->
			<PickModel v-if="provider && !switching" :provider="provider" @added="added" @switch="switching = true" />
			<ConnectSetup v-else :connected="connectedIds" @connected="connected" @use="use" @manual="create('providers')" />
		</template>
		<Button v-else-if="hasModels && canEnable" variant="solid" label="Enable an agent" @click="open('agents')" />
		<div v-else-if="!hasModels" class="flex flex-col items-center gap-3">
			<Button
				variant="solid"
				:label="asked ? 'Asked' : 'Ask an admin to connect Flow'"
				:icon-left="asked ? 'lucide-check' : 'lucide-bell'"
				:disabled="Boolean(asked)"
				@click="ask"
			/>
			<p v-if="asked?.length" class="text-p-sm text-ink-gray-5">
				{{ asked.join(" and ") }} {{ asked.length > 1 ? "have" : "has" }} a note.
			</p>
		</div>
	</div>
</template>

<script setup>
import { computed, inject, ref } from "vue";
import { Button, toast } from "frappe-ui";
import BrandMark from "@flow/ui-core/components/BrandMark.vue";

import { call } from "../api/frappe.js";
import ConnectSetup from "./setup/ConnectSetup.vue";
import PickModel from "./setup/PickModel.vue";

// The empty state until a model and an agent exist: what is missing, and who can add it.
// Connecting a provider is a few clicks; finishing it is the chat.
const flow = inject("flow");
const page = inject("flowPage");
const hasModels = computed(() => page.state.boot.models.length > 0);
const canConnect = computed(
	() => !hasModels.value && page.can("Flow Provider", "create") && page.can("Flow Model", "create")
);
const canEnable = computed(() => page.can("Flow Agent", "write"));
// the provider just connected or picked again, else the one boot names
const connectedNow = ref(null);
const provider = computed(() => connectedNow.value ?? page.state.boot.providers?.[0]);
// those connected already, ticked when another is chosen: boot's, and any connected here before
// boot is fetched again
const connectedHere = ref([]);
const connectedIds = computed(() => [...new Set([...(page.state.boot.providers ?? []), ...connectedHere.value])]);
const switching = ref(false); // connecting another provider in place of the one there

// the greeting a colleague would give, by the hour and the first name
const greeting = computed(() => {
	const hour = new Date().getHours();
	const hello = hour < 5 ? "Hello" : `Good ${hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening"}`;
	const name = page.state.boot.user?.full_name?.split(" ")[0];
	return name ? `${hello}, ${name}` : hello;
});
const subline = computed(() => {
	if (canConnect.value && provider.value && !switching.value) return "Pick the model chats start with.";
	if (canConnect.value) return "Connect a provider to get started.";
	if (!hasModels.value) return "An admin needs to connect a provider first.";
	return canEnable.value
		? "Every model is set, but no agent is enabled."
		: "Ask an administrator to enable an agent.";
});

// connected: boot names the provider, and its models are picked from
function connected({ service }) {
	use(service);
	connectedHere.value.push(connectedNow.value);
	page.changed("Flow Provider");
	toast.success(`${service.name} is connected for everyone`);
}

// Ollama is saved under LiteLLM's name for its chat endpoint
function use(service) {
	connectedNow.value = service.id === "ollama" ? "ollama_chat" : service.id;
	switching.value = false;
}

// a model that answered: boot lists it, the composer appears, and the Assistant has its model
function added() {
	page.changed("Flow Model");
}

// someone who can't connect asks those who can; the note says who heard
const asked = ref(null);
let asking = false;
async function ask() {
	if (asking) return;
	asking = true;
	try {
		asked.value = (await call("frappe.flow.api.setup.ask_admin")).admins;
	} catch (error) {
		toast.error(error.message);
	} finally {
		asking = false;
	}
}

// settings on a tab
function open(tab) {
	page.state.settingsTab = tab;
	flow.setSettingsOpen(true);
}

// a server of one's own opens settings on a blank provider, not the list
function create(tab) {
	page.createRecord(tab);
	flow.setSettingsOpen(true);
}
</script>
