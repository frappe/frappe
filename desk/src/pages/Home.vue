<template>
	<header class="sticky top-0 z-10 flex items-center justify-between border-b bg-white px-5 py-2.5">
		<router-link to="/" class="flex cursor-pointer">
			<AppLogo class="h-7 w-7" />
		</router-link>
	</header>
</template>

<script setup>
import AppLogo from "@/components/icons/AppLogo.vue"
</script>
