<template>
	<div class="h-full">
		<FrappeUIProvider>
			<router-view v-slot="{ Component }">
				<keep-alive>
					<component :is="Component" />
				</keep-alive>
			</router-view>
		</FrappeUIProvider>
	</div>
</template>

<script setup lang="ts">
import { inject, onMounted, onBeforeUnmount } from "vue"
import { FrappeUIProvider } from "frappe-ui"
import useStudioStore from "@/stores/studioStore"

const store = useStudioStore()
const socket = inject<any>("socket")
const onDocUpdate = (info: any) => store.applyDiskSync(info)

onMounted(() => socket?.on("studio_doc_update", onDocUpdate))
onBeforeUnmount(() => socket?.off("studio_doc_update", onDocUpdate))
</script>
