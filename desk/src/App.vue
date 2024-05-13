<template>
	<div class="bg-white antialiased">
		<router-view v-if="['Login', 'Home'].includes($route.name)" />
		<ModuleShell v-else-if="session.isLoggedIn" />

		<!-- For global use -->
		<IconsTimeless />
		<IconsEspresso />
	</div>
</template>

<script setup>
import ModuleShell from "@/components/ModuleShell.vue"
import IconsTimeless from "@/components/icons/IconsTimeless.vue"
import IconsEspresso from "@/components/icons/IconsEspresso.vue"

import { inject } from "vue"

const session = inject("$session")
</script>
