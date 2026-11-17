<template>
	<!-- a model's form, for what the list leaves out (its title, extra params, who may use it) -->
	<DocForm
		v-if="view === 'model'"
		:spec="SPECS.models"
		:name="editing"
		:title="__('Edit model')"
		:back="__('Back to models')"
		@saved="load"
		@deleted="leave"
		@close="leave"
	/>
	<!-- a provider's form: a server or gateway's address, or removing one -->
	<DocForm
		v-else-if="view === 'provider'"
		:spec="SPECS.providers"
		:name="editing"
		:title="editing ? __('Edit provider') : __('Custom provider')"
		:back="__('Back to models')"
		@saved="(doc) => (editing = doc.name)"
		@deleted="leave"
		@close="leave"
	/>
	<SettingsPage
		v-else-if="view === 'connect'"
		:title="connectTitle"
		:description="connecting ? '' : __('Pick one, then add the models chats can use.')"
		:back="__('Back')"
		@back="setup?.back()"
	>
		<ConnectSetup
			ref="setup"
			:service="editing"
			:connected="services.map((service) => service.name)"
			:show-back="false"
			list
			@picked="(service) => (connecting = service)"
			@connected="connected"
			@manual="openProvider(null)"
			@cancel="leave"
		/>
	</SettingsPage>

	<SettingsPage v-else :title="__('Models')" :description="__('Providers and their models.')">
		<template v-if="canConnect && (services.length || other.length)" #actions>
			<Button variant="solid" :label="__('Connect provider')" @click="connect(null)" />
		</template>
		<LoadingState v-if="!loaded" class="justify-center py-8 text-sm text-ink-gray-5" />
		<!-- nothing connected: the one way in, in the middle -->
		<div v-else-if="!services.length && !other.length" class="flex flex-col items-center gap-2 py-16 text-center">
			<span class="mb-1 grid size-11 place-items-center rounded-7 bg-surface-gray-2 text-ink-gray-7">
				<span class="lucide-server size-5" aria-hidden="true" />
			</span>
			<p class="text-base-medium text-ink-gray-9">{{ __("No providers yet") }}</p>
			<p class="mb-2 max-w-[360px] text-balance text-base text-ink-gray-5">
				{{ canConnect ? __("Connect a provider, then add the models chats can use.") : __("An admin needs to connect a provider first.") }}
			</p>
			<Button v-if="canConnect" variant="solid" :label="__('Connect provider')" icon-left="lucide-plus" @click="connect(null)" />
		</div>
		<div v-else class="flex flex-col gap-6">
			<section v-for="service in services" :key="service.name" class="flex flex-col gap-2">
				<!-- the provider: its mark, name and count, adding a model and its menu on the right -->
				<div class="flex min-h-7 items-center gap-2">
					<ProviderIcon :provider-id="iconOf(service.name)" :size="18" bare class="flex-none" />
					<span class="min-w-0 truncate text-base-medium text-ink-gray-9">{{ service.label }}</span>
					<span class="flex-none text-sm text-ink-gray-5">{{ countOf(service.models) }}</span>
					<Badge v-if="!service.enabled" :label="__('Off')" theme="gray" />
					<span class="flex-1" />
					<!-- one more model, picked off the provider's own list -->
					<Combobox
						v-if="canCreateModel && service.enabled"
						trigger="button"
						:options="addable(service)"
						:loading="listing === service.name"
						:disabled="Boolean(adding[service.name])"
						:model-value="null"
						:placeholder="__('Search or type a model id')"
						:empty-text="__('No other models from {0}', [service.label])"
						align="end"
						data-add-model
						@update:open="(open) => open && opened(service.name)"
						@update:model-value="(id) => id && add(service, id)"
					>
						<template #item-label="{ item }">
							<div class="truncate" :title="item.label">{{ item.label }}</div>
						</template>
						<template #trigger>
							<Button variant="ghost" icon-left="lucide-plus" :label="__('Add model')" :aria-label="__('Add a model from {0}', [service.label])" />
						</template>
						<template #item-typed="{ query }">{{ __("Use “{0}”", [query.trim()]) }}</template>
					</Combobox>
					<Dropdown v-if="providerMenu(service).length" :options="providerMenu(service)" align="end">
						<Button variant="ghost" icon="lucide-ellipsis" :aria-label="__('{0} settings', [service.label])" />
					</Dropdown>
				</div>
				<!-- the model picked is asked first, and listed only once it answers; one that didn't
				     isn't added, and why shows until Add model opens again -->
				<p v-if="adding[service.name]" class="flex items-center gap-1.5 text-sm text-ink-gray-5">
					<span class="lucide-loader-circle size-3.5 animate-spin" aria-hidden="true" />
					{{ __("Checking {0}…", [adding[service.name]]) }}
				</p>
				<ErrorMessage v-else-if="addErrors[service.name]" class="break-words" :message="addErrors[service.name]" />
				<p
					v-if="!service.models.length"
					class="rounded-6 border border-dashed border-outline-gray-2 py-6 text-center text-sm text-ink-gray-5"
				>
					{{ __("No models yet.") }}
				</p>
				<ul v-else class="divide-y divide-outline-gray-1 overflow-hidden rounded-6 border border-outline-gray-2">
					<ModelRow
						v-for="model in service.models"
						:key="model.name"
						:model="model"
						:paused="!service.enabled"
						:can-write="canWriteModel"
						@toggle="(on) => toggle(model, on)"
						@open="openModel(model.name)"
					/>
				</ul>
			</section>
			<!-- models that carry a key of their own, set up without a provider -->
			<section v-if="other.length" class="flex flex-col gap-2">
				<div class="flex min-h-7 items-center gap-2">
					<span class="text-base-medium text-ink-gray-9">{{ __("With their own key") }}</span>
					<span class="text-sm text-ink-gray-5">{{ countOf(other) }}</span>
				</div>
				<ul class="divide-y divide-outline-gray-1 overflow-hidden rounded-6 border border-outline-gray-2">
					<ModelRow
						v-for="model in other"
						:key="model.name"
						:model="model"
						:can-write="canWriteModel"
						@toggle="(on) => toggle(model, on)"
						@open="openModel(model.name)"
					/>
				</ul>
			</section>
		</div>
		<ErrorMessage :message="error" class="mt-3" />
	</SettingsPage>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { Badge, Button, Combobox, Dropdown, ErrorMessage, dialog, toast } from "frappe-ui";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";
import ProviderIcon from "@flow/ui-core/components/ProviderIcon.vue";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";
import { __ } from "@flow/ui-core/translate.js";

import { call } from "../api/frappe.js";
import ConnectSetup from "../chat/setup/ConnectSetup.vue";
import { addableModels, serviceFor } from "../chat/setup/services.js";
import DocForm from "./DocForm.vue";
import ModelRow from "./ModelRow.vue";
import { SPECS } from "./specs.js";

// Models, by the provider they come from, on one tab. Connecting a provider adds no model: Add
// model picks each from the provider's own list, and a switch takes one out of use. A model is asked
// one message before it's added, so one that doesn't work is never listed.
const page = inject("flowPage");

const view = ref("list"); // list | connect | model | provider
const editing = ref(null); // the model or provider a page is about
const services = ref([]);
const other = ref([]);
const loaded = ref(false);
const error = ref("");
const listing = ref(null);
const known = ref({}); // provider → its model ids, asked once
const adding = reactive({}); // provider → the model being checked before it's added
const addErrors = reactive({}); // provider → why the model last picked wasn't added
const setup = ref(null);
const connecting = ref(null); // the provider the key is for, named in the page's heading
const connectTitle = computed(() => {
	if (!connecting.value) return __("Connect a provider");
	return editing.value ? __("New key for {0}", [connecting.value.name]) : __("Connect {0}", [connecting.value.name]);
});

const canConnect = computed(() => page.can("Flow Provider", "create") && page.can("Flow Model", "create"));
const canWriteProvider = computed(() => page.can("Flow Provider", "write"));
const canDeleteProvider = computed(() => page.can("Flow Provider", "delete") && page.can("Flow Model", "delete"));
const canWriteModel = computed(() => page.can("Flow Model", "write"));
const canCreateModel = computed(() => page.can("Flow Model", "create"));

// Ollama is saved under LiteLLM's name for its chat endpoint
const iconOf = (provider) => (provider === "ollama_chat" ? "ollama" : provider);
const countOf = (models) => (models.length === 1 ? __("1 model") : models.length ? __("{0} models", [models.length]) : "");

async function load() {
	try {
		const result = await call("frappe.flow.api.setup.services");
		services.value = result.services;
		other.value = result.other;
		error.value = "";
	} catch (failure) {
		error.value = failure.message;
	}
	loaded.value = true;
}
onMounted(load);

function leave() {
	view.value = "list";
	editing.value = null;
	connecting.value = null;
	load();
}

function connect(provider) {
	editing.value = provider;
	view.value = "connect";
}

function openModel(name) {
	editing.value = name;
	view.value = "model";
}

function openProvider(name) {
	editing.value = name;
	view.value = "provider";
}

// connected, the provider shows with no models, its Add model ready
function connected({ service }) {
	page.changed("Flow Provider");
	toast.success(__("{0} is connected", [service.name]));
	leave();
}

// the switch moves at once; a failed save puts it back
async function toggle(model, on) {
	const was = model.enabled;
	model.enabled = on ? 1 : 0;
	try {
		await call("frappe.client.set_value", {
			doctype: "Flow Model",
			name: model.name,
			fieldname: "enabled",
			value: on ? 1 : 0,
		});
		page.changed("Flow Model");
	} catch (failure) {
		model.enabled = was;
		return toast.error(failure.message);
	}
}

// Add model opening: the last one's failure goes, and the provider's list is asked for
function opened(provider) {
	addErrors[provider] = "";
	list(provider);
}

// the provider's list, asked once; the models it has already are left out
async function list(provider) {
	if (known.value[provider]) return;
	listing.value = provider;
	known.value[provider] = await call("frappe.flow.doctype.flow_model.flow_model.get_provider_models", {
		provider,
	}).catch(() => []);
	listing.value = null;
}
function addable(service) {
	const saved = new Set(service.models.map((model) => model.model_id));
	return addableModels(service.name, known.value[service.name] ?? [], saved, (id) => add(service, id));
}
// the server asks it one message and saves it only if it answers; its row comes then
async function add(service, id) {
	adding[service.name] = id.slice(service.name.length + 1);
	addErrors[service.name] = "";
	try {
		const model = await call("frappe.flow.api.setup.add_model", { provider: service.name, model_id: id });
		if (!model.check.ok) return (addErrors[service.name] = model.check.message);
		service.models.push(model);
		page.changed("Flow Model");
	} catch (failure) {
		addErrors[service.name] = failure.message;
	} finally {
		adding[service.name] = "";
	}
}

// a provider's own settings: its key or address, and turning it off
function providerMenu(service) {
	return [
		// one with an address of its own is edited, so its key isn't checked against the public service
		canConnect.value && serviceFor(service.name) && !service.base_url
			? { label: __("Change key"), icon: "lucide-key-round", onClick: () => connect(service.name) }
			: canWriteProvider.value && { label: __("Edit"), icon: "lucide-pencil", onClick: () => openProvider(service.name) },
		canWriteProvider.value && {
			label: service.enabled ? __("Turn off") : __("Turn on"),
			icon: service.enabled ? "lucide-power-off" : "lucide-power",
			onClick: () => setEnabled(service, !service.enabled),
		},
		// a provider goes with its models
		canDeleteProvider.value && {
			label: __("Delete"),
			icon: "lucide-trash-2",
			theme: "red",
			onClick: () => removeProvider(service),
		},
	].filter(Boolean);
}
function removeProvider(service) {
	const count = service.models.length;
	const label = service.label;
	let message = __("“{0}” will be permanently removed.", [label]);
	if (count === 1) message = __("“{0}” and its 1 model will be permanently removed.", [label]);
	else if (count) message = __("“{0}” and its {1} models will be permanently removed.", [label, count]);
	dialog.danger({
		title: __("Delete this provider?"),
		size: "lg",
		message,
		onConfirm: async ({ close }) => {
			try {
				await call("frappe.flow.api.setup.remove_provider", { provider: service.name });
				page.changed("Flow Provider");
				if (count) page.changed("Flow Model");
			} catch (failure) {
				toast.error(failure.message);
			}
			close();
			load();
		},
	});
}
async function setEnabled(service, on) {
	try {
		await call("frappe.client.set_value", {
			doctype: "Flow Provider",
			name: service.name,
			fieldname: "enabled",
			value: on ? 1 : 0,
		});
		page.changed("Flow Provider");
		await load();
	} catch (failure) {
		toast.error(failure.message);
	}
}
</script>
