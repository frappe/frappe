<template>
	<Dialog v-model="showDialog" :options="{ title: 'Studio Settings', width: 'md' }" @after-leave="reset">
		<template #body-content>
			<div class="flex flex-col gap-3">
				<FormControl
					label="OpenRouter API Key"
					type="password"
					variant="outline"
					v-model="apiKey"
					placeholder="sk-or-..."
				/>
				<FormControl
					label="AI Model"
					type="text"
					variant="outline"
					v-model="aiModel"
					placeholder="openrouter/google/gemini-3.1-pro-preview"
					:description="'litellm model string passed to OpenRouter'"
				/>
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
import { Dialog, FormControl, ErrorMessage, createDocumentResource } from "frappe-ui"
import { toast } from "vue-sonner"

const showDialog = defineModel("showDialog", { type: Boolean, required: true })

const apiKey = ref("")
const aiModel = ref("")
const error = ref("")
const saving = ref(false)

const settings = createDocumentResource({
	doctype: "Studio Settings",
	name: "Studio Settings",
	onSuccess(doc: any) {
		apiKey.value = doc.openrouter_api_key || ""
		aiModel.value = doc.ai_model
	},
})

watch(
	() => showDialog.value,
	(open) => {
		if (!open) return
		settings.reload()
		error.value = ""
	},
	{ immediate: true },
)

function reset() {
	apiKey.value = ""
	aiModel.value = ""
	error.value = ""
}

function save() {
	saving.value = true
	error.value = ""
	settings.setValue
		.submit({
			openrouter_api_key: apiKey.value,
			ai_model: aiModel.value,
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
