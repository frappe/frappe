<template>
	<div class="toolbar flex h-14 items-center justify-center bg-white p-2 shadow-sm">
		<div class="absolute left-3 flex items-center">
			<router-link class="flex items-center gap-2" :to="{ name: 'Home' }">
				<h1 class="text-md mt-[2px] font-semibold leading-5 text-gray-800">Studio</h1>
			</router-link>
		</div>

		<div class="absolute right-3 flex items-center">
			<Button
				size="sm"
				variant="solid"
				@click="
					() => {
						publishing = true
						store.publishPage().finally(() => (publishing = false))
					}
				"
			>
				Publish
			</Button>
		</div>
	</div>
</template>

<script setup lang="ts">
import { ref } from "vue"
import useStore from "@/store"

const store = useStore()
const publishing = ref(false)
</script>
