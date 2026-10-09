<template>
	<SettingsHeader title="Editor" description="Settings for Studio, shared across all apps">
		<template #actions>
			<Button variant="solid" label="Save" :loading="saving" :disabled="!isDirty" @click="save" />
		</template>
	</SettingsHeader>
	<SettingsBody>
		<div class="flex flex-col gap-4 pt-6">
			<ErrorMessage :message="error" />
			<FormControl label="OpenRouter API Key" type="password" variant="outline" v-model="apiKey" placeholder="sk-or-...">
				<template #description>
					<p class="text-xs leading-normal text-ink-gray-5">
						Get API key from
						<a href="https://openrouter.ai/keys" target="_blank" rel="noopener noreferrer" class="underline">
							openrouter.ai/keys
						</a>
						— supports Claude, Gemini, GPT and more under one key.
					</p>
				</template>
			</FormControl>
		</div>
	</SettingsBody>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from "vue"
import { Button, ErrorMessage, FormControl, SettingsBody, SettingsHeader, toast } from "frappe-ui"
import { studioSettings } from "@/data/studioSettings"

const apiKey = ref("")
const savedApiKey = computed(() => studioSettings.doc?.ai_api_key || "")
const isDirty = computed(() => apiKey.value !== savedApiKey.value)

const error = ref("")
const saving = ref(false)

onMounted(async () => {
	if (!studioSettings.doc) {
		await studioSettings.reload()
	}
	apiKey.value = savedApiKey.value
})

function save() {
	saving.value = true
	error.value = ""
	studioSettings.setValue
		.submit({ ai_api_key: apiKey.value })
		.then(() => {
			toast.success("Editor settings saved")
		})
		.catch((e: any) => {
			error.value = e?.message || "Failed to save settings"
		})
		.finally(() => {
			saving.value = false
		})
}
</script>
