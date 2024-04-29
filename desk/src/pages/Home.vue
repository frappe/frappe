<template>
	<header class="sticky top-0 z-10 flex w-full flex-col items-center border-b bg-white px-5 py-2.5">
		<div class="w-full max-w-5xl">
			<div class="flex w-full items-center justify-between">
				<router-link to="/" class="flex cursor-pointer">
					<AppLogo class="h-7 w-7" />
				</router-link>

				<div class="flex flex-row items-center justify-center">
					<AwesomeBar />
				</div>
			</div>
		</div>
	</header>
	<Desktop />
</template>

<script setup>
import AppLogo from "@/components/icons/AppLogo.vue"
import AwesomeBar from "@/components/AwesomeBar.vue"
import Desktop from "@/components/Desktop.vue"
</script>
