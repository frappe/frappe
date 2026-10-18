<template>
	<AccountAdd
		v-if="view === 'add'"
		:controller="controller"
		:providers="providers"
		@back="backToList('')"
		@created="onCreated"
		@dirty="(value) => (dirty = value)"
	/>
	<AccountEdit
		v-else-if="editing"
		:controller="controller"
		:account="editing"
		@back="backToList"
		@dirty="(value) => (dirty = value)"
	/>
	<AccountList
		v-else
		v-model:oauth-result="oauthResult"
		:oauth-mailbox="mailbox"
		:controller="controller"
		:focus="returnFocus"
		@add="view = 'add'"
		@open="(name) => (editing = controller.accounts.find((a) => a.name === name))"
	/>
</template>

<script setup lang="ts">
import { toast } from "frappe-ui";
import { h, onBeforeUnmount, onMounted, ref, shallowRef, watch } from "vue";
import { translate as __ } from "../../utils/translate";
import AccountAdd from "./AccountAdd.vue";
import AccountEdit from "./AccountEdit.vue";
import AccountList from "./AccountList.vue";
import { errorText, mailboxAddress, missingDefaults } from "./services";
import type { EmailAccount } from "./types";
import { useEmailAccounts } from "./useEmailAccounts";

const props = defineProps<{
	/** The DocType incoming mail is appended to, e.g. `"HD Ticket"`. */
	doctype: string;
	/** Email Account `service` values to offer tiles for, `""` being Custom email; all by default. */
	providers?: string[];
}>();
const emit = defineEmits<{
	/** A mailbox was added, with a password or API key or by one-click sign-in. */
	created: [service: string];
}>();
/**
 * Whether an add or edit form has unsaved changes; the host reads it to guard its own
 * navigation.
 */
const dirty = defineModel<boolean>("dirty", { default: false });

const controller = useEmailAccounts(props.doctype);

const landing = new URL(window.location.href);
const oauthResult = ref(landing.searchParams.get("email_oauth"));
const mailbox = mailboxAddress(landing.searchParams.get("email_oauth_mailbox"));
if (oauthResult.value) {
	landing.searchParams.delete("email_oauth");
	landing.searchParams.delete("email_oauth_mailbox");
	window.history.replaceState(window.history.state, "", landing);
}

const view = ref<"list" | "add">("list");
const editing = shallowRef<EmailAccount>();
watch(
	() => controller.accounts,
	(accounts) => {
		const name = editing.value?.name;
		editing.value = accounts.find((a) => a.name === name) ?? editing.value;
	}
);

const returnFocus = ref<string>();
function backToList(focus: string) {
	returnFocus.value = focus;
	dirty.value = false;
	view.value = "list";
	editing.value = undefined;
}

function onCreated(service: string) {
	backToList("");
	emit("created", service);
}

const connected = oauthResult.value === "connected";
if (connected || oauthResult.value === "reconnected") {
	const message = connected
		? mailbox
			? __("Connected {0}", [mailbox])
			: __("Mailbox connected")
		: mailbox
		? __("Reconnected {0}", [mailbox])
		: __("Mailbox reconnected");
	toast.success(() => h("span", message));
	oauthResult.value = null;
}

if (connected) {
	const stop = watch(
		() => controller.accounts,
		async (accounts) => {
			const account = accounts.find(
				(a) => a.email_id.toLowerCase() === mailbox?.toLowerCase()
			);
			if (!account) return;
			stop();
			emit("created", account.service);
			try {
				for (const kind of missingDefaults(accounts, account)) {
					await controller.setDefault(kind, account.name);
				}
			} catch (e) {
				toast.error(errorText(e) || __("Couldn't change the default account"));
			}
		}
	);
}

onMounted(() => controller.load());
onBeforeUnmount(() => (dirty.value = false));
</script>
