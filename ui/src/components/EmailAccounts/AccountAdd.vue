<template>
	<div class="flex h-full flex-col">
		<BackHeader
			ref="header"
			:title="title"
			:dirty="dirty"
			:disabled="saving || Boolean(connecting)"
			@back="back"
		>
			<template v-if="selected" #actions>
				<Button
					type="submit"
					:form="formId"
					variant="solid"
					:label="__('Create')"
					:loading="saving"
				/>
			</template>
		</BackHeader>
		<ScrollArea class="-mx-3 min-h-0 flex-1" viewport-class="px-3">
			<template v-if="selected">
				<form
					:id="formId"
					class="mt-6 flex flex-col gap-4"
					novalidate
					@submit.prevent="create"
				>
					<Banner
						v-if="unavailable"
						:title="__('{0} sign-in isn\'t available right now', [selected.label])"
						:description="__('You can still set it up manually.')"
					/>
					<p v-if="selected.help" class="text-p-sm text-ink-gray-6">
						{{ selected.help }}
						<a
							:href="selected.helpLink"
							target="_blank"
							rel="noopener"
							class="text-ink-gray-8 underline"
						>
							{{ __("Learn more") }}
							<span
								class="lucide-arrow-up-right inline-block size-3"
								aria-hidden="true"
							/>
							<span class="sr-only">{{ __("(opens in new tab)") }}</span>
						</a>
					</p>
					<fieldset :disabled="saving">
						<AccountFields v-model:form="form" :service="selected" :error="invalid" />
					</fieldset>
				</form>
			</template>
			<template v-else>
				<h3 :id="headingId" class="mb-3 mt-6 text-base-medium text-ink-gray-8">
					{{ __("Choose your email provider") }}
				</h3>
				<div
					ref="tiles"
					role="group"
					:aria-labelledby="headingId"
					class="grid grid-cols-1 gap-2 sm:grid-cols-3"
				>
					<Button
						v-for="s in offered"
						:key="s.service"
						variant="outline"
						class="[height:theme(spacing.11)] [justify-content:start] hover:border-outline-gray-4"
						:label="s.label"
						:loading="connecting === s"
						:disabled="Boolean(connecting) && connecting !== s"
						@click="choose(s)"
					>
						<template #prefix>
							<img
								v-if="s.logo"
								:src="s.logo"
								alt=""
								class="size-6 object-contain"
							/>
							<span
								v-else
								class="lucide-mail size-6 text-ink-gray-6"
								aria-hidden="true"
							/>
						</template>
					</Button>
				</div>
				<ErrorMessage v-if="connectError" class="mt-3" :message="connectError" />
			</template>
		</ScrollArea>
	</div>
</template>

<script setup lang="ts">
import { Button, ErrorMessage, ScrollArea, toast } from "frappe-ui";
import { computed, nextTick, ref, shallowRef, useId, watch } from "vue";
import { translate as __ } from "../../utils/translate";
import AccountFields from "./AccountFields.vue";
import BackHeader from "./BackHeader.vue";
import Banner from "./Banner.vue";
import { emptyForm, errorText, oneClickServices, services, validate } from "./services";
import type { EmailAccountsController, EmailService, FieldError } from "./types";

const props = defineProps<{ controller: EmailAccountsController; providers?: string[] }>();
const emit = defineEmits<{ back: []; created: [service: string]; dirty: [dirty: boolean] }>();

const offered = computed(() =>
	props.providers ? services.filter((s) => props.providers!.includes(s.service)) : services
);
const selected = shallowRef<EmailService | null>(null);
const connecting = shallowRef<EmailService | null>(null);
const connectError = ref<unknown>(null);
const unavailable = ref(false);
const headingId = useId();
const formId = useId();
const blank = JSON.stringify(emptyForm());
const form = ref(emptyForm());
const dirty = computed(() => JSON.stringify(form.value) !== blank);
watch(dirty, (value) => emit("dirty", value));
const invalid = ref<FieldError>();
const saving = ref(false);

async function choose(service: EmailService) {
	connectError.value = null;
	if (oneClickServices()[service.service]) {
		connecting.value = service;
		try {
			if (await props.controller.connect(service.service)) return;
		} catch (e) {
			connectError.value = e;
			connecting.value = null;
			await nextTick();
			if (document.activeElement === document.body)
				tiles.value?.querySelectorAll("button")[offered.value.indexOf(service)]?.focus();
			return;
		}
		connecting.value = null;
		unavailable.value = true;
	}
	selected.value = service;
	await nextTick();
	header.value?.focus();
}

const header = ref<{ focus(): void }>();
const title = computed(() => {
	const service = selected.value;
	if (!service) return __("New email account");
	if (service.kind === "custom") return __("New custom email account");
	return __("New {0} account", [service.label]);
});

const tiles = ref<HTMLElement>();
async function back() {
	if (!selected.value) return emit("back");
	const i = offered.value.indexOf(selected.value);
	selected.value = null;
	unavailable.value = false;
	form.value = emptyForm();
	invalid.value = undefined;
	await nextTick();
	tiles.value?.querySelectorAll("button")[i]?.focus();
}

async function create() {
	const service = selected.value!;
	invalid.value = validate(service, form.value);
	if (invalid.value) return;
	const focused = document.activeElement as HTMLElement | null;
	saving.value = true;
	try {
		await props.controller.create(service, form.value);
		toast.success(__("Email account created"));
		emit("created", service.service);
	} catch (e) {
		toast.error(errorText(e) || __("Couldn't create the email account"));
		saving.value = false;
		await nextTick();
		if (document.activeElement === document.body) focused?.focus();
	} finally {
		saving.value = false;
	}
}
</script>
