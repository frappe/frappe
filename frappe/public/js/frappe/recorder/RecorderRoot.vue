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

watch(route, () => {
	frappe.router.current_route = frappe.router.parse();
	frappe.breadcrumbs.update();
	frappe.recorder.route = route;
});
</script>
