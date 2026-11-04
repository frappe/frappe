<template>
	<!-- a model's form, for what the list leaves out (its title, extra params, who may use it) -->
	<DocForm
		v-if="view === 'model'"
		:spec="SPECS.models"
		:name="editing"
		title="Edit model"
		back="Back to models"
		@saved="load"
		@deleted="leave"
		@close="leave"
	/>
	<!-- a service's form: a server or gateway's address, or turning one off for good -->
	<DocForm
		v-else-if="view === 'provider'"
		:spec="SPECS.providers"
		:name="editing"
		:title="editing ? 'Edit service' : 'Your own server or gateway'"
		back="Back to models"
		@saved="savedProvider"
		@deleted="leave"
		@close="leave"
	/>
	<!-- adding models is picking where they come from; a new key is that service's key step alone -->
	<SettingsPage
		v-else-if="view === 'connect'"
		:title="connectTitle"
		:description="connecting ? billedBy(connecting) : 'Flow turns on its best models. You can add more after.'"
		back="Back"
		@back="setup?.back()"
	>
		<!-- the service's mark by its name, as on a sign-in page; a narrow frame has no room for it -->
		<template v-if="connecting && !layout.narrow" #actions>
			<ProviderIcon :provider-id="connecting.id" :size="28" bare />
		</template>
		<!-- the page's Back is the only one: out of a picked service first, then out of the page -->
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

	<SettingsPage v-else title="Models" description="The models Flow can use in chats, by the provider they come from.">
		<!-- a model is added in its provider's card; the page's own action is another provider -->
		<template v-if="(services.length || other.length) && canConnect" #actions>
			<Button variant="subtle" label="Connect provider" icon-left="lucide-plus" @click="connect(null)" />
		</template>
		<LoadingState v-if="!loaded" class="justify-center py-8 text-sm text-ink-gray-5" />
		<!-- one way in: with nothing connected, the action once, in the middle -->
		<div v-else-if="!services.length && !other.length" class="flex flex-col items-center gap-2 py-16 text-center">
			<span class="mb-1 grid size-11 place-items-center rounded-7 bg-surface-gray-2 text-ink-gray-7">
				<span class="lucide-server size-5" aria-hidden="true" />
			</span>
			<p class="text-base-medium text-ink-gray-9">Connect a provider to start</p>
			<p class="mb-2 max-w-[360px] text-base text-ink-gray-5">
				Flow turns on the provider's best models for you. You can add or switch off models after.
			</p>
			<Button v-if="canConnect" variant="solid" label="Connect a provider" icon-left="lucide-plus" @click="connect(null)" />
		</div>
		<!-- each provider a section: its mark, name and count with adding a model and its settings on
		     the right; its models as cards under it, side by side as the page's width allows -->
		<div v-else class="flex flex-col gap-8">
			<section v-for="service in services" :key="service.name" class="flex flex-col gap-3">
				<div class="flex min-h-8 items-center gap-2.5">
					<ProviderIcon :provider-id="iconOf(service.name)" :size="24" bare class="flex-none" />
					<span class="min-w-0 truncate text-base-medium text-ink-gray-9">{{ service.label }}</span>
					<span class="flex-none text-base text-ink-gray-5">{{ countOf(service) }}</span>
					<span v-if="keyRejected(service) || !service.enabled" class="flex-none text-sm text-ink-red-6">
						{{ !service.enabled ? "Turned off" : "Key rejected" }}
					</span>
					<span class="flex-1" />
					<!-- this provider's own list, to pick one more from -->
					<Combobox
						v-if="canCreateModel && service.enabled"
						trigger="button"
						:options="addable(service)"
						:loading="listing === service.name"
						:model-value="null"
						placeholder="Search models"
						:empty-text="`No other models from ${service.label}`"
						align="end"
						@update:open="(open) => open && list(service.name)"
						@update:model-value="(id) => id && add(service, id)"
					>
						<template #trigger>
							<!-- the trigger takes the combobox's click itself: a Tooltip around it would swallow it -->
							<Button
								variant="ghost"
								icon="lucide-plus"
								title="Add model"
								:aria-label="`Add a model from ${service.label}`"
							/>
						</template>
					</Combobox>
					<Dropdown v-if="providerMenu(service).length" :options="providerMenu(service)" align="end">
						<Button variant="ghost" icon="lucide-ellipsis" :aria-label="`${service.label} settings`" />
					</Dropdown>
				</div>
				<p v-if="!service.models.length" class="text-base text-ink-gray-5">No models yet. Add one with +.</p>
				<ul v-else class="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3">
					<ModelRow
						v-for="model in service.models"
						:key="model.name"
						:model="model"
						:subtitle="model.model_id"
						:paused="!service.enabled || keyRejected(service)"
						:checking="checking.has(model.name)"
						:passed="passed.has(model.name)"
						:can-write="canWriteModel"
						:can-delete="canDeleteModel"
						:rekey="canConnect && Boolean(serviceFor(service.name))"
						@toggle="(on) => toggle(model, on)"
						@open="openModel(model.name)"
						@retry="check(model)"
						@rekey="connect(service.name)"
						@remove="remove(service.models, model)"
					/>
				</ul>
			</section>
			<!-- models that carry a key of their own, set up before providers were -->
			<section v-if="other.length" class="flex flex-col gap-3">
				<div class="flex min-h-8 items-center gap-2.5">
					<span class="text-base-medium text-ink-gray-9">With their own key</span>
					<span class="text-base text-ink-gray-5">{{ countOf({ models: other }) }}</span>
				</div>
				<ul class="grid grid-cols-[repeat(auto-fill,minmax(280px,1fr))] gap-3">
					<ModelRow
						v-for="model in other"
						:key="model.name"
						:model="model"
						:subtitle="model.model_id"
						:checking="checking.has(model.name)"
						:passed="passed.has(model.name)"
						:can-write="canWriteModel"
						:can-delete="canDeleteModel"
						@toggle="(on) => toggle(model, on)"
						@open="openModel(model.name)"
						@retry="check(model)"
						@remove="remove(other, model)"
					/>
				</ul>
			</section>
		</div>
		<ErrorMessage :message="error" class="mt-3" />
	</SettingsPage>
</template>

<script setup>
import { computed, inject, onMounted, reactive, ref } from "vue";
import { Button, Combobox, Dropdown, ErrorMessage, toast } from "frappe-ui";
import LoadingState from "@flow/ui-core/components/LoadingState.vue";
import ProviderIcon from "@flow/ui-core/components/ProviderIcon.vue";
import SettingsPage from "@flow/ui-core/components/SettingsPage.vue";
import { layout } from "@flow/ui-core/layout.js";

import { call } from "../api/frappe.js";
import ConnectSetup from "../chat/setup/ConnectSetup.vue";
import { billedBy, serviceFor } from "../chat/setup/services.js";
import DocForm from "./DocForm.vue";
import ModelRow from "./ModelRow.vue";
import { SPECS } from "./specs.js";

// Models, by the service they come from, on one tab. Adding a service turns on its recommended
// models, so most never pick one; a switch takes one out of use, and Add model picks another from
// the service's own list. A model is asked one message when it's added or switched on, so whether
// it works is known here and not in the next chat.
const page = inject("flowPage");

const view = ref(page.takeNewRecord("providers") ? "provider" : "list"); // list | connect | model | provider
const editing = ref(null); // the model or service a page is about
const services = ref([]);
const other = ref([]);
const loaded = ref(false);
const error = ref("");
const listing = ref(null);
const known = ref({}); // service → its model ids, asked once
const checking = reactive(new Set()); // models being asked
const passed = reactive(new Set()); // models that answered since the tab opened
const setup = ref(null);
const connecting = ref(null); // the service the key step is for, named in the page's heading
const connectTitle = computed(() => {
	if (!connecting.value) return "Add a service";
	return editing.value ? `New key for ${connecting.value.name}` : `Connect ${connecting.value.name}`;
});

const canConnect = computed(() => page.can("Flow Provider", "create") && page.can("Flow Model", "create"));
const canWriteProvider = computed(() => page.can("Flow Provider", "write"));
const canWriteModel = computed(() => page.can("Flow Model", "write"));
const canCreateModel = computed(() => page.can("Flow Model", "create"));
const canDeleteModel = computed(() => page.can("Flow Model", "delete"));

// Ollama is saved under LiteLLM's name for its chat endpoint
const iconOf = (provider) => (provider === "ollama_chat" ? "ollama" : provider);

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

// a server saved from its form stays on the form, so its models can be added next on the list
function savedProvider(doc) {
	editing.value = doc.name;
	page.changed("Flow Provider");
}

// connecting checked the key with the service's first model, so its models open as working
function connected({ service, models }) {
	page.changed("Flow Model");
	toast.success(`${service.name} is connected. ${models.length === 1 ? "1 model is" : `${models.length} models are`} on`);
	models.forEach((name) => passed.add(name));
	leave();
}

// the model's answer to one message: a pass shows for now, a failure stays beside it (switched off)
async function check(model) {
	checking.add(model.name);
	passed.delete(model.name);
	try {
		model.check = await call("frappe.flow.api.setup.check_model", { name: model.name });
		if (model.check.ok) passed.add(model.name);
		else if (model.check.reason !== "unreachable") model.enabled = 0;
	} catch (failure) {
		model.check = { ok: false, message: failure.message };
	} finally {
		checking.delete(model.name);
		page.changed("Flow Model");
	}
}

// the switch and its badge move at once; a failed save puts them back
async function toggle(model, on) {
	const was = model.enabled;
	model.enabled = on ? 1 : 0;
	passed.delete(model.name);
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
	if (on) check(model);
}

async function remove(models, model) {
	try {
		await call("frappe.client.delete", { doctype: "Flow Model", name: model.name });
		models.splice(models.indexOf(model), 1);
		page.changed("Flow Model");
	} catch (failure) {
		toast.error(failure.message);
	}
}

// the service's list, asked when Add model opens; the models it has already are left out
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
	const prefix = `${service.name}/`;
	return (known.value[service.name] ?? [])
		.filter((id) => !saved.has(id))
		.map((id) => ({ label: id.slice(prefix.length), value: id }));
}
// the row is there at once, saying it's being added; the server saves it and asks it one message
async function add(service, id) {
	const pending = reactive({ name: `adding:${id}`, title: id.slice(service.name.length + 1), model_id: id, adding: true });
	service.models.push(pending);
	try {
		const model = await call("frappe.flow.api.setup.add_model", { provider: service.name, model_id: id });
		service.models.splice(service.models.indexOf(pending), 1, model);
		if (model.check.ok) {
			passed.add(model.name);
			toast.success(`${model.title} is added and works`);
		}
		page.changed("Flow Model");
	} catch (failure) {
		service.models.splice(service.models.indexOf(pending), 1);
		toast.error(failure.message);
	}
}

// a provider whose key its models were refused with; they wait on a new one
function keyRejected(service) {
	return service.models.some((model) => model.check && !model.check.ok && model.check.reason === "wrong_key");
}
// "2 models", by a provider's name
function countOf(service) {
	const n = service.models.length;
	return n ? `${n} ${n === 1 ? "model" : "models"}` : "";
}
// a provider's own settings, named for what they do: its key or address, and turning it off
function providerMenu(service) {
	return [
		canConnect.value && serviceFor(service.name)
			? { label: "Change key", icon: "lucide-key", onClick: () => connect(service.name) }
			: canWriteProvider.value && { label: "Edit address", icon: "lucide-pencil", onClick: () => openProvider(service.name) },
		canWriteProvider.value && {
			label: service.enabled ? "Turn off provider" : "Turn on provider",
			icon: service.enabled ? "lucide-power-off" : "lucide-power",
			onClick: () => setEnabled(service, !service.enabled),
		},
	].filter(Boolean);
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
