<template>
	<div>
		<ol>
			<li v-for="path in paths" :key="path">{{ path }}</li>
		</ol>
	</div>
</template>

<script>
export default {
	name: "recorder-app",
	data() {
		return {
			paths: [],
			id: "Hello, Vue.js !!!"
		};
	},
	mounted() {
		frappe.call("frappe.www.recorder.get_paths").then( r => {
			this.paths = r.message
		})
	}
};
</script>
