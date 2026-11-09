<template>
	<!-- the first run's last step: a connected provider, and the model to start with -->
	<div class="flex w-full max-w-[360px] flex-col gap-3 text-left">
		<div class="flex items-center gap-2.5">
			<ProviderIcon :provider-id="provider === 'ollama_chat' ? 'ollama' : provider" :size="18" bare />
			<p class="text-base-medium text-ink-gray-8">{{ name ? `Pick a ${name} model` : "Pick a model" }}</p>
		</div>
		<Combobox
			:options="options"
			:loading="!listed"
			:disabled="Boolean(adding)"
			:model-value="null"
			placeholder="Search or type a model id"
			@update:model-value="(id) => id && add(id)"
		>
			<template #item-typed="{ query }">Use “{{ query.trim() }}”</template>
		</Combobox>
		<p v-if="adding" class="flex items-center gap-1.5 text-sm text-ink-gray-5">
			<span class="lucide-loader-circle size-3.5 animate-spin" aria-hidden="true" />
			Checking {{ adding }}…
		</p>
		<ErrorMessage v-else class="break-words" :message="error" />
		<Button class="-ml-2 self-start" variant="ghost" label="Use another provider" :disabled="Boolean(adding)" @click="emit('switch')" />
	</div>
</template>

<script setup>
import { computed, onMounted, ref } from "vue";
import { Button, Combobox, ErrorMessage } from "frappe-ui";
import ProviderIcon from "@flow/ui-core/components/ProviderIcon.vue";

import { call } from "../../api/frappe.js";
import { addableModels, serviceFor } from "./services.js";

// The model the first chat starts with, from the connected `provider`'s list or typed. It is
// asked one message as it's added; one that answers emits `added`, one that doesn't says why and
// another can be picked. `switch` asks to connect another provider.
const props = defineProps({ provider: { type: String, required: true } });
const emit = defineEmits(["added", "switch"]);

const name = computed(() => serviceFor(props.provider)?.name ?? (props.provider === "ollama_chat" ? "Ollama" : ""));
const listed = ref(null);
const adding = ref(""); // the model being added and checked
const error = ref("");
const options = computed(() => addableModels(props.provider, listed.value ?? [], new Set(), add));

onMounted(async () => {
	listed.value = await call("frappe.flow.doctype.flow_model.flow_model.get_provider_models", {
		provider: props.provider,
	}).catch(() => []);
});

async function add(id) {
	adding.value = id.slice(props.provider.length + 1);
	error.value = "";
	try {
		const model = await call("frappe.flow.api.setup.add_model", { provider: props.provider, model_id: id, for_chat: 1 });
		if (model.check.ok) return emit("added", model);
		error.value = model.check.message;
	} catch (failure) {
		error.value = failure.message;
	} finally {
		adding.value = "";
	}
}
</script>
