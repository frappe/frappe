<template>
	<Dialog v-model="showDialog" :options="{ title: 'Studio Settings', size: 'lg' }" @after-leave="reset">
		<template #body-content>
			<div class="flex flex-col gap-3">
				<FormControl
					label="OpenRouter API Key"
					type="password"
					variant="outline"
					v-model="apiKey"
					placeholder="sk-or-..."
				>
					<template #description>
						<p class="text-xs leading-normal text-ink-gray-5">
							Get API key from
							<a
								href="https://openrouter.ai/keys"
								target="_blank"
								rel="noopener noreferrer"
								class="underline"
							>
								openrouter.ai/keys
							</a>
							— supports Claude, Gemini, GPT and more under one key.
						</p>
					</template>
				</FormControl>
			</div>
		</template>

		<template #actions>
			<div class="space-y-1">
				<ErrorMessage class="mb-2" :message="error" />
				<Button variant="solid" label="Save" @click="save" class="w-full" :loading="saving" />
			</div>
		</template>
	</Dialog>
</template>

<script lang="ts" setup>
import { ref, watch } from "vue"
import { Dialog, FormControl, ErrorMessage } from "frappe-ui"
import { toast } from "frappe-ui"
import { studioSettings } from "@/data/studioSettings"

const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const apiKey = ref("")
const error = ref("")
const saving = ref(false)

watch(
	() => showDialog.value,
	async (open) => {
		if (!open) return
		if (!studioSettings.doc) {
			await studioSettings.reload()
		}
		apiKey.value = studioSettings.doc?.ai_api_key || ""
		error.value = ""
	},
	{ immediate: true },
)

function reset() {
	apiKey.value = ""
	error.value = ""
}

function save() {
	saving.value = true
	error.value = ""
	studioSettings.setValue
		.submit({
			ai_api_key: apiKey.value,
		})
		.then(() => {
			showDialog.value = false
			toast.success("Studio Settings saved")
		})
		.catch((e: any) => {
			error.value = e?.message || "Failed to save settings"
		})
		.finally(() => {
			saving.value = false
		})
}
</script>
