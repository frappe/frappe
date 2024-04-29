<template>
	<div class="bg-white antialiased">
		<router-view />
		<IconsTimeless />
		<IconsEspresso />
	</div>
</template>

<script setup>
import IconsTimeless from "@/components/icons/IconsTimeless.vue"
import IconsEspresso from "@/components/icons/IconsEspresso.vue"
</script>
