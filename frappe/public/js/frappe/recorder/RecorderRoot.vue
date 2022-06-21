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
			frappe.breadcrumbs.update();
		}
	}
};
</script>
