<template>
	<header class="sticky top-0 z-10 flex w-full flex-col items-center border-b bg-white px-5 py-2.5">
		<div class="w-full" :class="isHome ? 'max-w-5xl' : ''">
			<div class="flex w-full items-center justify-between">
				<router-link v-if="isHome" to="/" class="flex cursor-pointer">
					<AppLogo class="h-7 w-7" />
				</router-link>

				<div class="flex w-full flex-row items-center justify-between">
					<Breadcrumbs :items="breadcrumbs" />
					<AwesomeBar class="ml-auto" />
				</div>
			</div>
		</div>
	</header>
</template>

<script setup>
import { computed } from "vue"
import { useRoute } from "vue-router"
import { Breadcrumbs } from "frappe-ui"

import AwesomeBar from "@/components/AwesomeBar.vue"
import AppLogo from "@/components/icons/AppLogo.vue"

import { useBreadcrumbs } from "@/composables/breadcrumbs"

const route = useRoute()
const isHome = computed(() => route.name === "Home")

const breadcrumbs = useBreadcrumbs(route)
</script>
