<template>
	<keep-alive include="RecorderDetail">
		<router-view/>
	</keep-alive>
</template>

<<<<<<< HEAD
<script>
export default {
	name: "RecorderRoot",
	watch: {
		$route() {
			frappe.router.current_route = frappe.router.parse();
			frappe.breadcrumbs.update();
		}
	}
};
=======
<script setup>
import { watch } from "vue"
import { useRoute } from "vue-router"

let route = useRoute();

watch(route, async () => {
	frappe.router.current_route = await frappe.router.parse();
	frappe.breadcrumbs.update();
	frappe.recorder.route = route;
});
>>>>>>> 22990ff343 (fix: use `async...await` when parsing route)
</script>
