<template>
	<div class="flex h-screen w-full items-center justify-center bg-surface-gray-1 p-4">
		<div class="flex max-w-lg flex-col items-center text-center">
			<span class="lucide-lock h-6 w-6 text-ink-gray-5" />
			<h1 class="mt-4 text-xl font-semibold text-ink-gray-8">Not Editable</h1>
			<p class="mt-2 text-base text-ink-gray-5">
				{{ app?.app_title || "This app" }} is a standard app and can only be edited in developer mode
			</p>
			<div class="mt-6 flex items-center gap-2">
				<Button variant="outline" label="Back to Dashboard" @click="$router.push({ name: 'Home' })" />
				<Button v-if="app?.route" variant="solid" label="View App" @click="viewApp" />
			</div>
		</div>
	</div>
</template>

<script setup lang="ts">
import { onActivated, ref } from "vue"
import { useRoute } from "vue-router"
import { Button } from "frappe-ui"
import { fetchApp } from "@/utils/helpers"
import type { StudioApp } from "@/types/Studio/StudioApp"

const route = useRoute()
const app = ref<StudioApp | null>(null)

// kept alive by App.vue, so reload the app each time the page is shown
onActivated(async () => {
	app.value = null
	app.value = await fetchApp(route.params.appID as string).catch(() => null)
})

function viewApp() {
	window.location.href = `/${app.value!.route}`
}
</script>
