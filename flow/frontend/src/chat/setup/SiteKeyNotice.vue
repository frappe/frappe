<template>
	<div class="flex w-full max-w-sm flex-col items-center gap-6 text-center">
		<p class="text-pretty text-p-base text-ink-gray-6">
			{{ NOTICE[0]
			}}<a :href="PROCESSORS_URL" target="_blank" rel="noopener" :class="LINK">{{ __("list of data processors") }}</a
			>{{ NOTICE[1] }}
		</p>
		<div class="flex flex-col items-center gap-3">
			<div class="flex flex-wrap justify-center gap-2">
				<Button variant="solid" :label="__('I understand, continue')" :loading="busy" @click="accept" />
				<Button :label="__('Reject')" :disabled="busy" @click="emit('rejected')" />
			</div>
			<ErrorMessage v-if="error" :message="error" />
			<p v-else class="text-sm text-ink-gray-5">{{ __("Reject to connect your own provider instead.") }}</p>
		</div>
	</div>
</template>

<script setup>
import { ref } from "vue";
import { Button, ErrorMessage } from "frappe-ui";
import { __ } from "@flow/ui-core/translate.js";

import { call } from "../../api/frappe.js";

const emit = defineEmits(["accepted", "rejected"]);
const busy = ref(false);
const error = ref("");

async function accept() {
	busy.value = true;
	error.value = "";
	try {
		const result = await call("frappe.flow.api.setup.use_site_key");
		if (result.ok) return emit("accepted");
		error.value = result.message;
	} catch (failure) {
		error.value = failure.message;
	} finally {
		busy.value = false;
	}
}

const PROCESSORS_URL = "https://docs.frappe.io/legal/data-protection/data-processors#proposed-ai-processors";
const NOTICE = __("Flow uses a third-party inference provider for its AI features. See the {0}.").split("{0}");
const LINK = "text-ink-gray-8 underline decoration-outline-gray-3 underline-offset-4 hover:decoration-outline-gray-6";
</script>
