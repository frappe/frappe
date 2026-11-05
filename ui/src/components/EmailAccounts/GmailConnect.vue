<template>
	<Dialog v-model:open="open" :title="__('Connect Gmail')" size="lg">
		<form :id="formId" class="flex flex-col gap-4" novalidate @submit.prevent="submit">
			<Banner
				v-if="unavailable"
				:title="__('Google sign-in isn\'t available right now')"
				:description="__('You can still connect with an app password.')"
			/>
			<Banner
				v-else-if="wrongMailbox"
				theme="red"
				:title="__('You signed in with another Google account')"
				:description="
					__(
						'That isn\'t the address you entered. Sign in with {0}, or set up manually.',
						[email]
					)
				"
			/>
			<FormControl
				v-model="email"
				type="email"
				:label="__('Email address')"
				placeholder="support@example.com"
				:description="__('The Gmail or Google Workspace email ID you\'re connecting.')"
				autofocus
				@blur="checked = email.trim()"
			/>
			<div
				v-if="kind === 'personal'"
				class="flex flex-wrap items-center gap-3 rounded-6 bg-surface-gray-1 p-3"
			>
				<div class="flex min-w-0 flex-1 basis-64 flex-col gap-1">
					<span class="text-base-medium text-ink-gray-8">
						{{ __("Personal Gmail connects with an app password") }}
					</span>
					<p class="text-p-base text-ink-gray-6">
						{{
							__(
								"Turn on 2-Step Verification, then create a 16-character app password in your Google Account."
							)
						}}
					</p>
				</div>
				<Button
					variant="outline"
					:href="APP_PASSWORD_HELP"
					icon-right="lucide-arrow-up-right"
					:label="__('How to create one')"
				/>
			</div>
			<section
				v-else-if="kind === 'company' && !unavailable"
				class="flex flex-col gap-3 rounded-6 border border-outline-gray-2 p-3"
			>
				<div class="flex items-start gap-3">
					<div class="flex min-w-0 flex-1 flex-col gap-1">
						<h4 class="text-base-medium text-ink-gray-8">
							{{ __("Your Google Workspace admin allows Frappe once") }}
						</h4>
						<p class="text-p-base text-ink-gray-6">
							{{
								__(
									"Follow these steps to continue. Skip this if your admin has already done it."
								)
							}}
						</p>
					</div>
					<Button
						variant="ghost"
						icon="lucide-copy"
						:tooltip="__('Copy steps for your admin')"
						:aria-label="__('Copy steps for your admin')"
						@click="copy(steps, __('Steps copied'))"
					/>
				</div>
				<ol class="flex list-decimal flex-col gap-5 pl-5 marker:text-ink-gray-6">
					<li v-for="(step, i) in stepItems" :key="i">
						<div class="flex min-w-0 flex-col gap-1">
							<span class="text-base-medium text-ink-gray-8">{{ step.title }}</span>
							<p class="text-p-base text-ink-gray-6">{{ step.description }}</p>
							<Button
								v-if="i === 0"
								class="self-start"
								variant="outline"
								:href="ADMIN_CONSOLE"
								icon-right="lucide-arrow-up-right"
								:label="__('Open Google Admin console')"
							/>
							<div
								v-if="i === 1 && clientId"
								class="flex items-center gap-1 rounded bg-surface-gray-1 py-1 pl-2 pr-1"
							>
								<code class="min-w-0 flex-1 truncate text-sm text-ink-gray-8">
									{{ clientId }}
								</code>
								<Button
									variant="ghost"
									size="sm"
									icon="lucide-copy"
									:tooltip="__('Copy client ID')"
									:aria-label="__('Copy client ID')"
									@click="copy(clientId, __('Client ID copied'))"
								/>
							</div>
						</div>
					</li>
				</ol>
			</section>
			<ErrorMessage v-if="error" :message="error" />
		</form>
		<template #actions>
			<div class="flex flex-col gap-2">
				<template v-if="kind === 'company' && !unavailable">
					<Button
						type="submit"
						:form="formId"
						variant="solid"
						size="md"
						:label="__('Sign in with Google')"
						:loading="connecting"
					/>
					<Button
						size="md"
						:label="__('Set up manually')"
						:disabled="connecting"
						@click="emit('manual', email)"
					/>
					<p class="text-center text-p-sm text-ink-gray-6">
						{{
							__(
								"Uses an app password from your Google Account instead of signing in."
							)
						}}
					</p>
				</template>
				<template v-else-if="kind === 'company'">
					<Button
						variant="solid"
						size="md"
						:label="__('Set up manually')"
						@click="emit('manual', email)"
					/>
					<p class="text-center text-p-sm text-ink-gray-6">
						{{
							__(
								"Uses an app password from your Google Account instead of signing in."
							)
						}}
					</p>
				</template>
				<template v-else>
					<Button
						type="submit"
						:form="formId"
						variant="solid"
						size="md"
						:label="__('Continue')"
						:disabled="!kindOf(email.trim())"
					/>
					<p v-if="kind" class="text-center text-p-sm text-ink-gray-6">
						{{ __("Opens the setup form with this address filled in.") }}
					</p>
				</template>
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { Button, Dialog, ErrorMessage, FormControl, toast } from "frappe-ui";
import { computed, ref, useId, watch } from "vue";
import { translate as __ } from "../../utils/translate";
import Banner from "./Banner.vue";
import { mailboxAddress } from "./services";
import type { EmailAccountsController } from "./types";

const APP_PASSWORD_HELP = "https://support.google.com/accounts/answer/185833";
const ADMIN_CONSOLE = "https://admin.google.com/ac/owl/list?tab=configuredApps";

const props = defineProps<{
	controller: EmailAccountsController;
	/** For a Google Workspace admin to allow; none when Frappe Cloud didn't send it. */
	clientId?: string | null;
	/** The address to start with. */
	initialEmail?: string;
	/** Whether the last sign-in for `initialEmail` came back with another account. */
	wrongMailbox?: boolean;
}>();
const emit = defineEmits<{ manual: [email: string] }>();
const open = defineModel<boolean>("open", { default: false });

const formId = useId();
const email = ref("");
/** The address as of the last blur or submit, which the steps and actions follow. */
const checked = ref("");
const wrongMailbox = ref(false);
const unavailable = ref(false);
const connecting = ref(false);
const error = ref<unknown>(null);

watch(
	open,
	(value) => {
		if (!value) return;
		email.value = props.initialEmail ?? "";
		checked.value = email.value;
		wrongMailbox.value = Boolean(props.wrongMailbox);
		unavailable.value = false;
		error.value = null;
	},
	{ immediate: true }
);
watch(email, (value) => {
	if (value !== props.initialEmail) wrongMailbox.value = false;
});

function kindOf(value: string) {
	const address = mailboxAddress(value);
	if (!address) return null;
	return /@(gmail|googlemail)\.com$/i.test(address) ? "personal" : "company";
}
const kind = computed(() => kindOf(checked.value));

const stepItems = computed(() => [
	{
		title: __("Open API controls in the Admin console"),
		description: __("Sign in as a Google Workspace admin."),
	},
	{
		title: __("Add Frappe as an app"),
		description: __("Click Configure new app and search for this client ID."),
	},
	{
		title: __("Choose who can connect mailboxes"),
		description: __("All users, or the group that has the support mailbox."),
	},
	{
		title: __("Set access to Trusted"),
		description: __(
			"Select Trusted and click Continue, then click Finish on the review screen."
		),
	},
]);
const steps = computed(() =>
	[
		__("Please allow Frappe to access Gmail for our team (one-time, about 2 minutes):"),
		"1. " +
			__("Open {0} (Security > API controls > Manage Third-Party App Access)", [
				ADMIN_CONSOLE,
			]),
		"2. " +
			(props.clientId
				? __("Click Configure new app and search for this client ID: {0}", [
						props.clientId,
				  ])
				: __("Click Configure new app and search for Frappe")),
		"3. " +
			__(
				"Choose who can connect mailboxes (all users, or the group with the support mailbox)"
			),
		"4. " + __("Select Trusted and click Continue, then click Finish on the review screen"),
	].join("\n")
);

async function copy(text: string, done: string) {
	try {
		await navigator.clipboard.writeText(text);
		toast.success(done);
	} catch {
		toast.error(__("Couldn't copy. Select the text and copy it yourself."));
	}
}

async function submit() {
	const address = email.value.trim();
	checked.value = address;
	if (!kind.value) return;
	if (kind.value === "personal" || unavailable.value) return emit("manual", address);
	error.value = null;
	connecting.value = true;
	try {
		if (await props.controller.connect("GMail", address)) return;
		unavailable.value = true;
	} catch (e) {
		error.value = e;
	}
	connecting.value = false;
}
</script>
