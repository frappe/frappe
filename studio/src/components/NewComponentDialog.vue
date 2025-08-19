<template>
	<Dialog v-model="showDialog" :options="{ title: 'Create Component', size: 'md' }" @after-leave="reset">
		<template #body-content>
			<div class="flex flex-col space-y-4">
				<FormControl label="Component Name" :required="true" v-model="componentName" autocomplete="off" />
			</div>
		</template>
		<template #actions>
			<div class="space-y-1">
				<ErrorMessage class="mb-2" :message="errorMessage" />
				<Button variant="solid" label="Create" @click="createComponent" class="w-full" />
			</div>
		</template>
	</Dialog>
</template>

<script setup lang="ts">
import { ref } from "vue"
import { Dialog, FormControl, ErrorMessage, Button } from "frappe-ui"
import useComponentStore from "@/stores/componentStore"

const showDialog = defineModel("showDialog", { type: Boolean, required: true })
const emit = defineEmits(["created"])
const componentName = ref("")
const errorMessage = ref("")

function reset() {
	componentName.value = ""
	errorMessage.value = ""
}

function createComponent() {
	if (!componentName.value) {
		errorMessage.value = "Please enter a Component Name"
		return
	}
	const componentStore = useComponentStore()
	componentStore.createComponent(componentName.value).then((data) => {
		if (data) {
			emit("created", data)
			reset()
			showDialog.value = false
		}
	})
}
</script>
