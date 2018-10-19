<template>
	<div>
		<ol>
			<li v-for="request in requests" :key="request.uuid">{{ request.uuid }}</li>
		</ol>
	</div>
</template>

<script>
export default {
	name: "recorder-path",
	data() {
		return {
			requests: [],
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_requests",
			args: {
				path: "/recorder"
			}
		}).then( r => {
			this.requests = r.message
		})
	}
};
</script>
