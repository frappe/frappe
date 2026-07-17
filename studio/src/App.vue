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

// Re-fetch the open editor when the folder watcher imports a disk edit (studio_disk_sync). Wired
// here in the editor root — not in the shared socket module — so the app renderer never pulls the
// editor store in.
const store = useStudioStore()
const socket = inject<any>("socket")
const onDiskSync = (info: any) => store.applyDiskSync(info)

onMounted(() => socket?.on("studio_disk_sync", onDiskSync))
onBeforeUnmount(() => socket?.off("studio_disk_sync", onDiskSync))
</script>
