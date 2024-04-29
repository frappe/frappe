<template>
	<header class="sticky top-0 z-10 flex w-full flex-col items-center border-b bg-white px-5 py-2.5">
		<div class="w-full max-w-5xl">
			<div class="flex w-full items-center justify-between">
				<router-link v-if="route.name === 'Home'" to="/" class="flex cursor-pointer">
					<AppLogo class="h-7 w-7" />
				</router-link>

				<div class="ml-auto flex flex-row items-center justify-center">
					<AwesomeBar />
				</div>
			</div>
		</div>
	</header>
</template>

<script setup>
import AwesomeBar from "@/components/AwesomeBar.vue"
import AppLogo from "@/components/icons/AppLogo.vue"
import { useRoute } from "vue-router"

const route = useRoute()
</script>
