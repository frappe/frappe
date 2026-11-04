<template>
	<!-- the first run inside the chat itself: a greeting, then the one thing missing and who can
	     add it. Connecting is a few clicks; finishing it is the chat. Hung from the top, not
	     centred: what changes below (a picked service, a key, an error) never moves the greeting -->
	<div class="flex w-full flex-1 flex-col items-center gap-8 self-stretch pb-10 pt-[min(18vh,160px)]">
		<div class="flex flex-col items-center gap-4 text-center">
			<BrandMark line :size="28" state="idle" />
			<div class="flex flex-col gap-1.5">
				<h1 class="text-2xl-semibold text-ink-gray-9">{{ greeting }}</h1>
				<p class="max-w-sm text-pretty text-p-base text-ink-gray-5">{{ subline }}</p>
			</div>
		</div>
		<ConnectSetup v-if="canConnect" @connected="connected" @manual="create('providers')" />
		<Button v-else-if="hasModels && canEnable" variant="solid" label="Enable an agent" @click="open('agents')" />
		<div v-else-if="!hasModels" class="flex flex-col items-center gap-3">
			<Button
				variant="solid"
				theme="gray"
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
import { useRouter } from "vue-router";
import { Button, toast } from "frappe-ui";
import BrandMark from "@flow/ui-core/components/BrandMark.vue";

import { call } from "../api/frappe.js";
import { inPanel } from "../panel.js";
import ConnectSetup from "./setup/ConnectSetup.vue";

// The empty state until a model and an agent exist: what is missing, and who can add it.
const flow = inject("flow");
const page = inject("flowPage");
const router = useRouter();
const hasModels = computed(() => page.state.boot.models.length > 0);
const canConnect = computed(
	() => !hasModels.value && page.can("Flow Provider", "create") && page.can("Flow Model", "create")
);
const canEnable = computed(() => page.can("Flow Agent", "write"));

// the greeting a colleague would give, by the hour and the first name
const greeting = computed(() => {
	const hour = new Date().getHours();
	const hello = hour < 5 ? "Hello" : `Good ${hour < 12 ? "morning" : hour < 17 ? "afternoon" : "evening"}`;
	const name = page.state.boot.user?.full_name?.split(" ")[0];
	return name ? `${hello}, ${name}` : hello;
});
const subline = computed(() => {
	if (canConnect.value) return "Set it up once, for everyone here.";
	if (!hasModels.value) return "An admin needs to connect an AI first.";
	return canEnable.value
		? "Every model is set, but no agent is enabled."
		: "Ask an administrator to enable an agent.";
});

// connected: boot lists the new models, the composer appears, and the Assistant has its model
function connected({ service }) {
	page.changed("Flow Model");
	toast.success(`${service.name} is connected for everyone`);
}

// someone who can't connect asks those who can; the note says who heard
const asked = ref(null);
async function ask() {
	try {
		asked.value = (await call("frappe.flow.api.setup.ask_admin")).admins;
	} catch (error) {
		toast.error(error.message);
	}
}

// settings on a tab; the launcher's panel opens its provider's form in place of the providers
function open(tab) {
	if (inPanel && tab === "providers") return router.push(`/providers/${page.state.boot.provider}`);
	page.state.settingsTab = tab;
	flow.setSettingsOpen(true);
}

// an Add step opens settings on a blank record, not the list; the launcher's panel opens the
// record's form in the chat's place, as an agent's, rather than settings over the whole window
function create(tab) {
	if (inPanel) return router.push(`/${tab}/new`);
	page.createRecord(tab);
	flow.setSettingsOpen(true);
}
</script>
