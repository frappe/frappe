<template>
	<div class="flex h-full flex-col">
		<div class="flex shrink-0 items-start justify-between gap-4">
			<div class="flex min-w-0 flex-col gap-1">
				<h2 :id="ids.heading" class="text-md-semibold text-ink-gray-8">
					{{ __("Email accounts") }}
				</h2>
				<p class="text-p-sm text-ink-gray-6">
					{{ __("Connect mailboxes to send and receive email.") }}
				</p>
			</div>
			<Button
				v-if="!controller.error"
				ref="newButton"
				class="shrink-0"
				variant="solid"
				icon-left="lucide-plus"
				:label="__('New')"
				@click="emit('add')"
			/>
		</div>
		<Banner
			v-if="oauthResult"
			class="mt-6 shrink-0"
			:theme="oauthResult === 'cancelled' ? 'gray' : 'red'"
			:title="
				oauthMailbox
					? __('Couldn\'t connect {0}', [oauthMailbox])
					: __('Couldn\'t connect the mailbox')
			"
			dismissible
			@dismiss="dismissResult"
		>
			<template #description>
				{{ oauthMessage(oauthResult) }}
				<a
					v-if="oauthResult === 'smtp_disabled'"
					href="https://learn.microsoft.com/en-us/exchange/clients-and-mobile-in-exchange-online/authenticated-client-smtp-submission#enable-smtp-auth-for-specific-mailboxes"
					target="_blank"
					rel="noopener"
					class="text-ink-gray-8 underline"
				>
					{{ __("How to turn it on") }}
					<span class="lucide-arrow-up-right inline-block size-3" aria-hidden="true" />
					<span class="sr-only">{{ __("(opens in new tab)") }}</span>
				</a>
			</template>
		</Banner>
		<div
			v-if="controller.loading && !controller.accounts.length && !controller.error"
			class="flex flex-1 items-center justify-center"
		>
			<Spinner size="lg" class="text-ink-gray-5" />
		</div>
		<div
			v-else-if="!controller.error && !controller.accounts.length"
			class="flex flex-1 flex-col items-center justify-center gap-2 text-center"
		>
			<span class="lucide-mail size-6 text-ink-gray-5" aria-hidden="true" />
			<p class="text-base-medium text-ink-gray-8">{{ __("No email accounts yet") }}</p>
			<p class="text-p-sm text-ink-gray-6">
				{{ __("Add one to start sending and receiving email.") }}
			</p>
			<Button class="mt-2" :label="__('New email account')" @click="emit('add')" />
		</div>
		<ScrollArea v-else class="-mx-3 min-h-0 flex-1" viewport-class="px-3">
			<Banner
				v-if="controller.error"
				ref="loadError"
				class="mt-6"
				theme="red"
				:title="__('Couldn\'t load email accounts')"
				:description="errorText(controller.error)"
			>
				<template #actions>
					<Button
						variant="outline"
						:label="__('Retry')"
						:loading="controller.loading"
						@click="retry"
					/>
				</template>
			</Banner>
			<template v-else>
				<p class="mt-6 text-sm text-ink-gray-5">
					{{ __("Email account name") }}
				</p>
				<ul
					ref="rows"
					:aria-labelledby="ids.heading"
					class="mt-2 divide-y divide-outline-gray-2 border-t border-outline-gray-2"
				>
					<li v-for="account in controller.accounts" :key="account.name">
						<div class="-mx-3 flex rounded-4 hover:bg-surface-gray-1">
							<!-- frappe-ui has no clickable list row; ItemListRow is for listboxes -->
							<button
								type="button"
								class="flex min-w-0 flex-1 items-center gap-3 rounded-4 px-3 text-start -outline-offset-2"
								@click="emit('open', account.name)"
							>
								<span class="flex h-14 min-w-0 flex-1 items-center gap-3">
									<Avatar size="xl">
										<img
											v-if="serviceOf(account).logo"
											:src="serviceOf(account).logo"
											alt=""
											class="size-full object-contain"
										/>
										<span
											v-else
											class="lucide-mail block size-full text-ink-gray-6"
											aria-hidden="true"
										/>
									</Avatar>
									<span class="flex min-w-0 flex-col">
										<span class="truncate text-base-medium text-ink-gray-7">
											{{ account.email_account_name }}
										</span>
										<span
											v-if="account.status === 'needs-reconnect'"
											class="mt-1 flex items-center gap-1 text-sm text-ink-amber-8"
										>
											<span
												class="lucide-triangle-alert size-3.5 shrink-0"
												aria-hidden="true"
											/>
											<span class="truncate">
												{{
													reconnectable(account)
														? __("Mailbox signed out. Reconnect it.")
														: __(
																"Mailbox signed out. Reconnect it in Desk."
														  )
												}}
											</span>
										</span>
										<span v-else class="mt-1 truncate text-sm text-ink-gray-5">
											{{ subtitle(account) }}
										</span>
									</span>
								</span>
								<Badge
									v-if="manualSetup(account)"
									theme="gray"
									:label="__('Manual setup')"
								/>
								<Badge v-bind="statusBadge(account)" />
							</button>
						</div>
					</li>
				</ul>

				<h3 class="mt-8 text-base-semibold text-ink-gray-9">
					{{ __("Default settings") }}
				</h3>
				<!-- SettingsRow can't take the smaller text-p-sm description these settings use -->
				<div class="flex flex-col divide-y divide-outline-gray-2">
					<div class="flex items-center gap-8 py-3.5">
						<div class="min-w-0 flex-1">
							<label
								:for="ids.incoming"
								class="block text-base-medium leading-tighter text-ink-gray-8"
							>
								{{ __("Default incoming") }}
							</label>
							<p class="mt-1 text-p-sm text-ink-gray-6">
								{{
									__(
										"If enabled, all replies to your company (eg: replies@yourcompany.com) will come to this account. Note: Only one account can be default incoming."
									)
								}}
							</p>
						</div>
						<Select
							:id="ids.incoming"
							:model-value="defaultOf('incoming')"
							:options="defaultOptions('enable_incoming')"
							class="w-56 shrink-0"
							align="end"
							@update:model-value="(v) => setDefault('incoming', v)"
						/>
					</div>
					<div class="flex items-center gap-8 py-3.5">
						<div class="min-w-0 flex-1">
							<label
								:for="ids.outgoing"
								class="block text-base-medium leading-tighter text-ink-gray-8"
							>
								{{ __("Default outgoing") }}
							</label>
							<p class="mt-1 text-p-sm text-ink-gray-6">
								{{
									__(
										"If enabled, all outgoing emails will be sent from this account. Note: Only one account can be default outgoing."
									)
								}}
							</p>
						</div>
						<Select
							:id="ids.outgoing"
							:model-value="defaultOf('outgoing')"
							:options="defaultOptions('enable_outgoing')"
							class="w-56 shrink-0"
							align="end"
							@update:model-value="(v) => setDefault('outgoing', v)"
						/>
					</div>
				</div>
			</template>
		</ScrollArea>
	</div>
</template>

<script lang="ts">
import type { FunctionalComponent } from "vue";

const logoIcons = new Map<string, FunctionalComponent>();
</script>

<script setup lang="ts">
import { Avatar, Badge, Button, ScrollArea, Select, Spinner, toast } from "frappe-ui";
import { h, nextTick, onMounted, reactive, ref, useId } from "vue";
import { translate as __ } from "../../utils/translate";
import Banner from "./Banner.vue";
import {
	errorText,
	manualSetup,
	oauthMessage,
	reconnectable,
	serviceOf,
	statusBadge,
	subtitle,
} from "./services";
import type { EmailAccount, EmailAccountsController } from "./types";

const props = defineProps<{
	controller: EmailAccountsController;
	/** On mount, focus this account's row, or for "" the New button, or Retry if loading failed. */
	focus?: string;
	/** The mailbox the sign-in result is about, when it is known. */
	oauthMailbox?: string | null;
}>();
const emit = defineEmits<{ add: []; open: [name: string] }>();
const oauthResult = defineModel<string | null>("oauthResult");
const ids = { heading: useId(), incoming: useId(), outgoing: useId() };

const newButton = ref<{ $el: HTMLElement }>();
const loadError = ref<{ $el: HTMLElement }>();
const rows = ref<HTMLElement>();
onMounted(() => {
	if (props.focus === undefined) return;
	const i = props.controller.accounts.findIndex((a) => a.name === props.focus);
	(rows.value?.querySelectorAll("li button")[i] ?? newOrRetry())?.focus();
});

function newOrRetry() {
	return newButton.value?.$el ?? loadError.value?.$el.querySelector("button");
}

async function retry() {
	await props.controller.load();
	await nextTick();
	if (document.activeElement === document.body) newOrRetry()?.focus();
}

function dismissResult() {
	oauthResult.value = null;
	newOrRetry()?.focus();
}

function defaultOf(kind: "incoming" | "outgoing") {
	return (
		pending[kind] ?? props.controller.accounts.find((a) => a[`default_${kind}`])?.name ?? ""
	);
}

function defaultOptions(enabled: "enable_incoming" | "enable_outgoing") {
	return [
		{ label: __("None"), value: "" },
		...props.controller.accounts
			.filter((a) => a[enabled])
			.map((a) => ({ label: a.email_account_name, value: a.name, icon: logoIcon(a) })),
	];
}

function logoIcon(account: EmailAccount) {
	const logo = serviceOf(account).logo;
	if (!logo) return "lucide-mail";
	let icon = logoIcons.get(logo);
	if (!icon) {
		icon = () => h("img", { src: logo, alt: "", class: "object-contain" });
		logoIcons.set(logo, icon);
	}
	return icon;
}

const pending = reactive<{ incoming?: string; outgoing?: string }>({});
async function setDefault(kind: "incoming" | "outgoing", name: string | number | null) {
	const value = name ? String(name) : "";
	if (pending[kind] !== undefined || value === defaultOf(kind)) return;
	pending[kind] = value;
	try {
		await props.controller.setDefault(kind, value || null);
		if (kind === "incoming") {
			toast.success(
				value
					? __("Default incoming account updated")
					: __("Default incoming account cleared")
			);
		} else {
			toast.success(
				value
					? __("Default outgoing account updated")
					: __("Default outgoing account cleared")
			);
		}
	} catch (e) {
		toast.error(errorText(e) || __("Couldn't change the default account"));
	} finally {
		pending[kind] = undefined;
	}
}
</script>
