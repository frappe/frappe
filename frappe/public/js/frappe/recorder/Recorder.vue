<template>
	<div>
		<ol>
			<li v-for="path in paths" :key="path.path">{{ path.path }} {{ path.count }}</li>
		</ol>
	</div>
</template>

<script>
export default {
	name: "recorder-app",
	data() {
		return {
			paths: [],
		};
	},
	mounted() {
		frappe.call("frappe.www.recorder.get_paths").then( r => {
			this.paths = r.message
		})
	}
};
</script>
