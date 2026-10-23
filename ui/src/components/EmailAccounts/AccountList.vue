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
				{{ oauthMessage(oauthResult, oauthProvider) }}
				<a
					v-if="helpLink"
					:href="helpLink"
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
				<div class="mt-6 grid grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-4">
					<div class="flex min-w-0 flex-col gap-1.5">
						<label :for="ids.incoming" class="text-sm text-ink-gray-7">
							{{ __("Default incoming") }}
						</label>
						<Select
							:id="ids.incoming"
							:model-value="defaultOf('incoming')"
							:options="defaultOptions('enable_incoming')"
							align="end"
							@update:model-value="(v) => setDefault('incoming', v)"
						/>
					</div>
					<div class="flex min-w-0 flex-col gap-1.5">
						<label :for="ids.outgoing" class="text-sm text-ink-gray-7">
							{{ __("Default outgoing") }}
						</label>
						<Select
							:id="ids.outgoing"
							:model-value="defaultOf('outgoing')"
							:options="defaultOptions('enable_outgoing')"
							align="end"
							@update:model-value="(v) => setDefault('outgoing', v)"
						/>
					</div>
				</div>

				<div class="mt-8 flex items-center gap-2">
					<h3 :id="ids.mailboxes" class="text-base-semibold text-ink-gray-8">
						{{ __("Mailboxes") }}
					</h3>
					<Badge theme="gray" :label="String(controller.accounts.length)" />
				</div>
				<ul
					ref="rows"
					:aria-labelledby="ids.mailboxes"
					class="mt-3 grid grid-cols-[repeat(auto-fill,minmax(16rem,1fr))] gap-4 pb-4"
				>
					<li
						v-for="(account, i) in controller.accounts"
						:key="account.name"
						class="flex min-w-0 flex-col overflow-hidden rounded-6 border border-outline-gray-2"
					>
						<!-- frappe-ui has no clickable card; ItemListRow is for listboxes -->
						<button
							type="button"
							data-open
							class="flex min-w-0 items-center gap-3 rounded-t-6 p-3 text-start -outline-offset-2 hover:bg-surface-gray-1"
							@click="emit('open', account.name)"
						>
							<Avatar size="lg">
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
							<span class="flex min-w-0 flex-1 flex-col gap-1">
								<span
									:id="`${ids.mailboxes}-${i}`"
									class="line-clamp-2 text-base-medium text-ink-gray-8 [overflow-wrap:anywhere]"
								>
									<!-- a long address breaks before its domain, not mid-word -->
									<template
										v-for="(part, j) in account.email_account_name.split('@')"
										:key="j"
										><wbr v-if="j" />{{ j ? "@" : "" }}{{ part }}</template
									>
								</span>
								<span class="truncate text-sm text-ink-gray-5">
									{{
										manualSetup(account)
											? `${subtitle(account)} · ${__("Manual setup")}`
											: subtitle(account)
									}}
								</span>
							</span>
							<Badge
								v-if="account.status === 'needs-reconnect'"
								class="shrink-0 self-start"
								theme="amber"
								:label="__('Needs reconnect')"
							/>
							<Badge
								v-else-if="!account.enable_incoming && !account.enable_outgoing"
								class="shrink-0 self-start"
								theme="gray"
								:label="__('Disabled')"
							/>
						</button>
						<div
							role="group"
							:aria-labelledby="`${ids.mailboxes}-${i}`"
							class="flex min-h-11 flex-wrap items-center gap-x-5 gap-y-2 border-t border-outline-gray-2 px-3 py-2"
						>
							<template v-if="account.status === 'needs-reconnect'">
								<span
									class="flex min-w-0 flex-1 items-start gap-1.5 text-p-sm text-ink-amber-8"
								>
									<span
										class="lucide-triangle-alert size-4 shrink-0"
										aria-hidden="true"
									/>
									{{ __("Mailbox signed out, mail has stopped") }}
								</span>
								<Button
									v-if="reconnectable(account)"
									class="shrink-0"
									variant="solid"
									:label="__('Reconnect')"
									:loading="reconnecting === account.name"
									:disabled="Boolean(reconnecting)"
									@click="reconnect(account, $event)"
								/>
								<Button
									v-else
									class="shrink-0"
									variant="outline"
									icon-right="lucide-arrow-up-right"
									:href="deskUrl(account.name)"
								>
									{{ __("Open in Desk") }}
									<span class="sr-only">{{ __("(opens in new tab)") }}</span>
								</Button>
							</template>
							<template v-else>
								<Switch
									control-position="start"
									:label="__('Receive')"
									:model-value="Boolean(account.enable_incoming)"
									:disabled="
										serviceOf(account).outgoingOnly ||
										saving.has(account.name + 'enable_incoming')
									"
									@update:model-value="
										(on) => toggle(account, 'enable_incoming', on)
									"
								/>
								<Switch
									control-position="start"
									:label="__('Send')"
									:model-value="Boolean(account.enable_outgoing)"
									:disabled="saving.has(account.name + 'enable_outgoing')"
									@update:model-value="
										(on) => toggle(account, 'enable_outgoing', on)
									"
								/>
							</template>
						</div>
					</li>
				</ul>
			</template>
		</ScrollArea>
	</div>
</template>

<script lang="ts">
import type { FunctionalComponent } from "vue";

const logoIcons = new Map<string, FunctionalComponent>();
</script>

<script setup lang="ts">
import { Avatar, Badge, Button, ScrollArea, Select, Spinner, Switch, toast } from "frappe-ui";
import { computed, h, nextTick, onMounted, reactive, ref, useId } from "vue";
import { translate as __ } from "../../utils/translate";
import Banner from "./Banner.vue";
import {
	deskUrl,
	errorText,
	manualSetup,
	oauthHelpLink,
	oauthMessage,
	reconnectable,
	serviceOf,
	subtitle,
} from "./services";
import type { EmailAccount, EmailAccountsController } from "./types";

const props = defineProps<{
	controller: EmailAccountsController;
	/** On mount, focus this account's row, or for "" the New button, or Retry if loading failed. */
	focus?: string;
	/** The mailbox the sign-in result is about, when it is known. */
	oauthMailbox?: string | null;
	/** The provider the sign-in went to, when it is known. */
	oauthProvider?: string | null;
}>();
const emit = defineEmits<{ add: []; open: [name: string] }>();
const oauthResult = defineModel<string | null>("oauthResult");
const helpLink = computed(
	() => oauthResult.value && oauthHelpLink(oauthResult.value, props.oauthProvider)
);
const ids = { heading: useId(), incoming: useId(), outgoing: useId(), mailboxes: useId() };

const newButton = ref<{ $el: HTMLElement }>();
const loadError = ref<{ $el: HTMLElement }>();
const rows = ref<HTMLElement>();
onMounted(() => {
	if (props.focus === undefined) return;
	const i = props.controller.accounts.findIndex((a) => a.name === props.focus);
	(rows.value?.querySelectorAll<HTMLElement>("[data-open]")[i] ?? newOrRetry())?.focus();
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

const saving = reactive(new Set<string>());
async function toggle(
	account: EmailAccount,
	field: "enable_incoming" | "enable_outgoing",
	on: boolean
) {
	const key = account.name + field;
	saving.add(key);
	try {
		// turning a direction off also clears the account's default for it, on save
		await props.controller.update(account, { [field]: on ? 1 : 0 });
	} catch (e) {
		toast.error(errorText(e) || __("Couldn't update the email account"));
	} finally {
		saving.delete(key);
	}
}

const reconnecting = ref<string>();
async function reconnect(account: EmailAccount, event: MouseEvent) {
	const button = event.currentTarget as HTMLElement;
	reconnecting.value = account.name;
	try {
		await props.controller.reconnect(account);
	} catch (e) {
		toast.error(errorText(e) || __("Couldn't connect. Please try again."));
		reconnecting.value = undefined;
		await nextTick();
		if (document.activeElement === document.body) button.focus();
	}
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
