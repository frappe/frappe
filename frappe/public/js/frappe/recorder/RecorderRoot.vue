<template>
	<keep-alive include="RecorderDetail">
		<router-view />
	</keep-alive>
</template>

<script>
export default {
	name: "RecorderRoot",
	watch: {
		async $route() {
			frappe.router.current_route = await frappe.router.parse();
			frappe.breadcrumbs.update();
		},
	},
};
</script>
