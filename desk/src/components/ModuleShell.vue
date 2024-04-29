<template>
	<div class="flex flex-row">
		<ModuleSidebar />
		<div class="flex grow flex-col">
			<Navbar />
			<router-view></router-view>
		</div>
	</div>
</template>

<script setup>
import ModuleSidebar from "@/components/ModuleSidebar.vue"
import Navbar from "@/components/Navbar.vue"
</script>
