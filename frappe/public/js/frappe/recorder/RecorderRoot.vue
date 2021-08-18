<template>
	<keep-alive include="RecorderDetail">
		<router-view/>
	</keep-alive>
</template>

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
</script>
