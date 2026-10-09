<template>
	<div class="flex flex-col gap-2 px-[2px]">
		<Input
			label="OpenRouter API Key"
			type="password"
			placeholder="sk-or-..."
			:modelValue="studioSettings.doc?.ai_api_key"
			:hideClearButton="true"
			@update:modelValue="save"
		/>
		<p class="text-p-sm text-ink-gray-6">
			Get an API key from
			<a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" class="underline">
				openrouter.ai/keys
			</a>
			— supports Claude, Gemini, GPT and more under one key.
		</p>
	</div>
</template>

<script setup lang="ts">
import { onMounted } from "vue"
import { toast } from "frappe-ui"
import Input from "@/components/Input.vue"
import { studioSettings } from "@/data/studioSettings"

onMounted(() => {
	if (!studioSettings.doc) studioSettings.reload()
})

function save(apiKey: string) {
	studioSettings.setValue
		.submit({ ai_api_key: apiKey })
		.then(() => toast.success("API key saved"))
		.catch((error: any) => toast.error("Could not save the API key", { description: error?.message }))
}
</script>
