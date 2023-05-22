<template>
	<router-view v-slot="{ Component }">
		<keep-alive>
			<component :is="Component"></component>
		</keep-alive>
	</router-view>
</template>

<script setup>
import { watch } from "vue"
import { useRoute } from "vue-router"

let route = useRoute();

watch(route, async () => {
	frappe.router.current_route = await frappe.router.parse();
	frappe.breadcrumbs.update();
	frappe.recorder.route = route;
});
</script>
