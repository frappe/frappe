<template>
	<div
		ref="root"
		class="relative flex flex-col gap-6 [&_[data-slot=error]]:absolute [&_[data-slot=error]]:text-sm"
	>
		<FormControl
			v-model="form.email_account_name"
			:label="__('Account name')"
			:placeholder="__('Support')"
			:error="errorOn('email_account_name')"
			required
		/>
		<FormControl
			v-model="form.email_id"
			type="email"
			:label="__('Email address')"
			placeholder="support@example.com"
			:disabled="oauth"
			:error="errorOn('email_id')"
			:required="!oauth"
		/>
		<template v-if="!oauth">
			<template v-if="service.kind === 'frappe-mail'">
				<FormControl
					v-model="form.frappe_mail_site"
					:label="__('Frappe Mail site')"
					placeholder="https://frappemail.com"
					:error="errorOn('frappe_mail_site')"
					required
				/>
				<FormControl
					v-model="form.api_key"
					:label="__('API key')"
					:error="errorOn('api_key')"
					required
				/>
				<Password
					v-model="form.api_secret"
					:label="__('API secret')"
					autocomplete="new-password"
					:description="editing ? __('Leave blank to keep the saved one.') : undefined"
					:error="errorOn('api_secret')"
					:required="!editing"
				/>
			</template>
			<Password
				v-else
				v-model="form.password"
				:label="__('Password')"
				autocomplete="new-password"
				:description="editing ? __('Leave blank to keep the saved one.') : undefined"
				:error="errorOn('password')"
				:required="!editing"
			/>
		</template>
		<template v-if="service.kind === 'custom'">
			<Link
				v-model="form.domain"
				doctype="Email Domain"
				:label="__('Email domain')"
				:placeholder="__('Search email domains')"
				:description="__('Leave empty to enter the server settings yourself.')"
				:error="errorOn('domain')"
				creatable
				redirectable
				@create="(query) => openDesk(`new?domain_name=${encodeURIComponent(query)}`)"
				@redirect="(name) => openDesk(encodeURIComponent(name))"
			/>
			<div v-if="!form.domain" class="grid grid-cols-1 gap-x-4 gap-y-6 sm:grid-cols-2">
				<div class="flex flex-col gap-6">
					<FormControl
						v-model="form.email_server"
						:label="__('Incoming server (IMAP)')"
						placeholder="imap.example.com"
						:error="errorOn('email_server')"
						:required="form.enable_incoming"
					/>
					<FormControl
						v-model="form.incoming_port"
						type="number"
						:label="__('Incoming port')"
					/>
					<Switch v-model="form.use_ssl" :label="__('Use SSL for incoming')" />
					<Switch
						v-if="!form.use_ssl"
						v-model="form.use_starttls"
						:label="__('Use STARTTLS for incoming')"
					/>
				</div>
				<div class="flex flex-col gap-6">
					<FormControl
						v-model="form.smtp_server"
						:label="__('Outgoing server (SMTP)')"
						placeholder="smtp.example.com"
						:error="errorOn('smtp_server')"
						:required="form.enable_outgoing"
					/>
					<FormControl
						v-model="form.smtp_port"
						type="number"
						:label="__('Outgoing port')"
					/>
					<Switch
						v-model="form.use_ssl_for_outgoing"
						:label="__('Use SSL for outgoing')"
					/>
					<Switch v-model="form.use_tls" :label="__('Use TLS for outgoing')" />
				</div>
			</div>
		</template>
		<div class="flex flex-col divide-y divide-outline-gray-2">
			<SettingsRow
				v-if="!service.outgoingOnly"
				:title="__('Receive email')"
				:description="__('Pull incoming email from this mailbox.')"
			>
				<Switch v-model="form.enable_incoming" />
			</SettingsRow>
			<SettingsRow
				:title="__('Send email')"
				:description="__('Send outgoing email through this mailbox.')"
			>
				<Switch v-model="form.enable_outgoing" />
			</SettingsRow>
		</div>
	</div>
</template>

<script setup lang="ts">
import { FormControl, Password, SettingsRow, Switch } from "frappe-ui";
import { ref, watch } from "vue";
import { Link } from "../Link";
import { translate as __ } from "../../utils/translate";
import type { AccountForm, EmailService, FieldError } from "./types";

const props = defineProps<{
	service: EmailService;
	/** Secrets may stay blank, keeping the saved ones. */
	editing?: boolean;
	/** Signed in with OAuth, so there are no credentials to edit. */
	oauth?: boolean;
	/** A problem `validate()` found, shown on its field, which takes focus. */
	error?: FieldError;
}>();
const form = defineModel<AccountForm>("form", { required: true });
const root = ref<HTMLElement>();

watch(
	() => props.error,
	() => root.value?.querySelector<HTMLElement>('[aria-invalid="true"]')?.focus(),
	{ flush: "post" }
);

function errorOn(field: FieldError["field"]) {
	return props.error?.field === field ? props.error.message : undefined;
}

function openDesk(path: string) {
	window.open(`/desk/email-domain/${path}`, "_blank", "noopener");
}
</script>
