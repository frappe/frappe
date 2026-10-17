<template>
	<div class="flex h-full flex-col">
		<BackHeader
			:title="account.email_account_name"
			:dirty="dirty"
			:disabled="saving || connecting"
			@back="emit('back', account.name)"
		>
			<template #actions>
				<Button
					v-if="account.enable_incoming && account.status !== 'needs-reconnect'"
					:label="__('Pull emails')"
					:loading="pulling"
					:disabled="saving"
					@click="pull"
				/>
				<Button
					type="submit"
					:form="formId"
					variant="solid"
					:label="__('Save')"
					:disabled="!dirty"
					:loading="saving"
				/>
			</template>
		</BackHeader>
		<ScrollArea class="-mx-3 min-h-0 flex-1" viewport-class="px-3">
			<div class="mt-6 flex items-center gap-3">
				<img
					v-if="service.logo"
					:src="service.logo"
					alt=""
					class="size-6 object-contain"
				/>
				<span v-else class="lucide-mail size-6 text-ink-gray-6" aria-hidden="true" />
				<span class="truncate text-base text-ink-gray-7">
					{{ subtitle(account) }}
				</span>
			</div>
			<Banner
				v-if="account.status === 'needs-reconnect'"
				class="mt-4"
				theme="amber"
				:title="
					reconnectable || account.authKind === 'oauth'
						? __('This mailbox needs to be reconnected')
						: __('This mailbox needs to be authorized again')
				"
				:description="
					reconnectable
						? __('Sign in again to keep email flowing.')
						: account.authKind === 'oauth'
						? __('Reconnect it in Desk.')
						: __('It uses its own OAuth app. Authorize it again in Desk.')
				"
			>
				<template #actions>
					<Button
						v-if="reconnectable"
						variant="outline"
						:label="__('Reconnect')"
						:loading="connecting"
						:disabled="saving"
						@click="confirmReconnect"
					/>
					<Button
						v-else
						variant="outline"
						icon-right="lucide-arrow-up-right"
						:href="deskUrl(account.name)"
					>
						{{ __("Open in Desk") }}
						<span class="sr-only">{{ __("(opens in new tab)") }}</span>
					</Button>
				</template>
			</Banner>

			<form :id="formId" class="mt-6 flex flex-col gap-4" novalidate @submit.prevent="save">
				<fieldset :disabled="saving">
					<AccountFields
						v-model:form="form"
						:service="service"
						:oauth="account.auth_method === 'OAuth'"
						:error="invalid"
						editing
					/>
				</fieldset>
			</form>
		</ScrollArea>
	</div>
</template>

<script setup lang="ts">
import { Button, ScrollArea, toast } from "frappe-ui";
import { computed, nextTick, ref, useId, watch } from "vue";
import { translate as __ } from "../../utils/translate";
import AccountFields from "./AccountFields.vue";
import BackHeader from "./BackHeader.vue";
import Banner from "./Banner.vue";
import { confirmDiscard } from "./confirmDiscard";
import {
	credentials,
	deskUrl,
	emptyForm,
	errorText,
	reconnectable as oneClickReconnect,
	serviceOf,
	subtitle,
	validate,
} from "./services";
import type { EmailAccount, EmailAccountsController, FieldError } from "./types";

const props = defineProps<{ controller: EmailAccountsController; account: EmailAccount }>();
const emit = defineEmits<{ back: [name: string]; dirty: [dirty: boolean] }>();

const service = computed(() => serviceOf(props.account));
const reconnectable = computed(() =>
	oneClickReconnect(props.account, props.controller.oneClickProviders)
);
const formId = useId();

const form = ref(emptyForm(props.account));
const changes = computed(() => {
	const saved = credentials(service.value, emptyForm(props.account));
	return Object.fromEntries(
		Object.entries(credentials(service.value, form.value)).filter(
			([field, value]) => saved[field] !== value
		)
	);
});
const renamed = computed(() => form.value.email_account_name !== props.account.email_account_name);
const dirty = computed(() => renamed.value || Object.keys(changes.value).length > 0);
watch(dirty, (value) => emit("dirty", value));

const invalid = ref<FieldError>();
const saving = ref(false);
async function save() {
	invalid.value = validate(
		service.value,
		form.value,
		true,
		props.account.auth_method === "OAuth"
	);
	if (invalid.value) return;
	const focused = document.activeElement as HTMLElement | null;
	saving.value = true;
	const newName = renamed.value ? form.value.email_account_name : undefined;
	try {
		await props.controller.update(props.account, changes.value, newName);
		toast.success(__("Email account saved"));
		emit("back", newName ?? props.account.name);
	} catch (e) {
		toast.error(errorText(e) || __("Couldn't save the email account"));
		saving.value = false;
		await nextTick();
		if (document.activeElement === document.body) focused?.focus();
	} finally {
		saving.value = false;
	}
}

const connecting = ref(false);
async function reconnect(button: HTMLElement) {
	connecting.value = true;
	try {
		await props.controller.connect(service.value.oneClick!, props.account.name);
	} catch (e) {
		toast.error(errorText(e) || __("Couldn't connect. Please try again."));
		connecting.value = false;
		await nextTick();
		if (document.activeElement === document.body) button.focus();
	}
}

function confirmReconnect(e: MouseEvent) {
	const button = e.currentTarget as HTMLElement;
	if (!dirty.value) return reconnect(button);
	confirmDiscard(
		__("Are you sure you want to leave? Unsaved changes will be lost."),
		() => reconnect(button),
		() => button.focus()
	);
}

const pulling = ref(false);
async function pull(event: MouseEvent) {
	const button = event.currentTarget as HTMLElement;
	pulling.value = true;
	try {
		await props.controller.pull(props.account.name);
		toast.success(__("Emails pulled"));
	} catch (e) {
		toast.error(errorText(e) || __("Couldn't pull emails"));
	} finally {
		pulling.value = false;
		await nextTick();
		if (document.activeElement === document.body) button.focus();
	}
}
</script>
