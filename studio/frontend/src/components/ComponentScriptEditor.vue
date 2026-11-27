<template>
	<div v-if="componentDoc" class="flex flex-col gap-2">
		<p class="text-sm text-ink-gray-5">
			The script of {{ componentDoc.component_name }}. Its default export declares the props, the emits
			and the setup function.
		</p>
		<ErrorMessage v-if="error" :message="error" />
		<Code
			:key="componentDoc.name"
			:modelValue="componentDoc.script || COMPONENT_SCRIPT_BOILERPLATE"
			language="javascript"
			valueMode="text"
			maxHeight="calc(100vh - 14rem)"
			:showLineNumbers="true"
			:showSaveButton="true"
			@save="save"
		/>
	</div>
	<EmptyState v-else message="Open a component to edit its script" />
</template>

<script setup lang="ts">
import { computed, ref } from "vue"
import { ErrorMessage, toast } from "frappe-ui"
import Code from "@/components/Code.vue"
import EmptyState from "@/components/EmptyState.vue"
import { checkAppScript } from "@/browserRuntime/appRuntime"
import { studioComponents } from "@/data/studioComponents"
import useCanvasStore from "@/stores/canvasStore"
import useComponentStore from "@/stores/componentStore"
import { COMPONENT_SCRIPT_BOILERPLATE } from "@/utils/constants"

/** The script of the open global component, for an editor with no app and so no files. */
const componentStore = useComponentStore()
const canvasStore = useCanvasStore()
const componentDoc = computed(() =>
	canvasStore.editingMode === "component"
		? componentStore.getComponentDoc(canvasStore.fragmentData.fragmentId ?? "")
		: null,
)
const error = ref("")

async function save(script: string) {
	error.value = (await checkAppScript(script, "component.js", true)) || ""
	if (error.value || !componentDoc.value) return
	try {
		const data = await studioComponents.setValue.submit({ name: componentDoc.value.name, script })
		await componentStore.cacheComponent(data)
		toast.success("Script saved")
	} catch (failure: any) {
		toast.error("Failed to save the script", { description: failure?.messages?.join(", ") })
	}
}
</script>
