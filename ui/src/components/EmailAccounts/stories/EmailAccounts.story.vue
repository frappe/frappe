<template>
	<div class="p-6">
		<div class="mb-4 flex flex-wrap items-center gap-4">
			<Switch v-model="cloud" label="Frappe Cloud (one-click Outlook)" />
			<Switch v-model="empty" label="No accounts" />
			<Select
				:model-value="null"
				label="Land from sign-in"
				:options="results"
				class="w-56"
				@update:model-value="land"
			/>
		</div>
		<div class="h-[640px] rounded-4 border border-outline-gray-2 px-10 py-8">
			<EmailAccounts :key="`${cloud}-${empty}-${landings}`" doctype="ToDo" />
		</div>
	</div>
</template>

<script setup lang="ts">
import { Select, Switch, getCachedResource } from "frappe-ui";
import { onBeforeUnmount, ref, watch } from "vue";
import EmailAccounts from "../EmailAccounts.vue";
import type { EmailAccountDoc } from "../types";

const cloud = ref(true);
const empty = ref(false);
const landings = ref(0);
watch(cloud, () => getCachedResource("one_click_email_services")?.reload());
const results = [
	"connected",
	"reconnected",
	"cancelled",
	"smtp_disabled",
	"wrong_mailbox",
	"not_team_member",
];

const base = {
	enable_incoming: 1,
	enable_outgoing: 1,
	default_incoming: 0,
	default_outgoing: 0,
} as const;
const accounts: EmailAccountDoc[] = [
	{
		...base,
		name: "Support",
		email_account_name: "Support",
		email_id: "support@example.com",
		service: "Outlook.com",
		auth_method: "OAuth",
		connected_app: "relay-support",
		token_uri: "frappe-cloud-relay:microsoft",
		default_incoming: 1,
		default_outgoing: 1,
	},
	{
		...base,
		name: "Billing",
		email_account_name: "Billing",
		email_id: "billing@example.com",
		service: "Outlook.com",
		auth_method: "OAuth",
		connected_app: "relay-billing",
		token_uri: "frappe-cloud-relay:microsoft",
	},
	{
		...base,
		name: "Legacy",
		email_account_name: "Legacy",
		email_id: "legacy@example.com",
		service: "Outlook.com",
		auth_method: "OAuth",
		connected_app: "own-app",
		token_uri: "https://login.microsoftonline.com/token",
		enable_outgoing: 0,
	},
	{
		...base,
		name: "Sales",
		email_account_name: "Sales",
		email_id: "sales@example.com",
		service: "GMail",
		auth_method: "Basic",
		enable_incoming: 0,
	},
	{
		...base,
		name: "Archive",
		email_account_name: "Archive",
		email_id: "archive@example.com",
		service: "",
		auth_method: "Basic",
		enable_incoming: 0,
		enable_outgoing: 0,
		email_server: "imap.example.com",
		smtp_server: "smtp.example.com",
	},
];

// sign-in lands on the page with these in the URL; the panel reads them when it mounts
function land(code: string | number | null) {
	const url = new URL(location.href);
	url.searchParams.set("email_oauth", String(code));
	url.searchParams.set("email_oauth_mailbox", "support@example.com");
	history.replaceState(history.state, "", url);
	landings.value++;
}

type Args = Record<string, any>;
const answers: Record<string, (args: Args) => unknown> = {
	"frappe.client.get_list": () => (empty.value ? [] : accounts),
	has_token: (args) => !["relay-billing", "own-app"].includes(args.connected_app),
	"frappe.client.set_value": ({ name, fieldname, value }) => {
		if (typeof fieldname !== "string") return;
		for (const a of accounts)
			if (a.name === name || value)
				Object.assign(a, { [fieldname]: a.name === name ? value : 0 });
	},
	get_one_click_services: () => (cloud.value ? { "Outlook.com": "Outlook" } : {}),
	initiate_mailbox_connect: (args) =>
		args.email_account || args.service === "Outlook.com" ? "#" : null,
	run_doc_method: () => "#",
};

// the panel fetches from Frappe itself, so the story answers its requests
const realFetch = window.fetch;
window.fetch = async (input, init) => {
	const method = String(input).match(/\/api\/method\/([^?]+)/)?.[1];
	if (!method) return realFetch(input, init);
	const answer = Object.entries(answers).find(([m]) => method.endsWith(m))?.[1];
	await new Promise((r) => setTimeout(r, 300));
	const message = answer?.(init?.body ? JSON.parse(String(init.body)) : {}) ?? null;
	// run_doc_method sends the document back with its result
	const docs = method.endsWith("run_doc_method") ? { docs: [] } : {};
	return new Response(JSON.stringify({ ...docs, message }), {
		headers: { "Content-Type": "application/json" },
	});
};
onBeforeUnmount(() => (window.fetch = realFetch));
</script>
