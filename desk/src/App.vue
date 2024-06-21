<template>
	<div class="bg-white antialiased">
		<router-view v-if="$route.name === 'Home' || $route.name === 'Login'" />
		<ModuleShell v-else-if="session?.isLoggedIn" />

		<!-- For global use -->
		<IconsTimeless />
		<IconsEspresso />
	</div>
</template>

<script setup lang="ts">
import ModuleShell from "@/components/ModuleShell.vue"
import IconsTimeless from "@/components/Icons/IconsTimeless.vue"
import IconsEspresso from "@/components/Icons/IconsEspresso.vue"

import { inject } from "vue"
import { Session } from "@/types"

const session = inject<Session>("$session")
</script>
