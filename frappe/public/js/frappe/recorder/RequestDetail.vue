<template>
	<div>
		<div v-for="call in calls" :key="call.function">
			{{ call }}
		</div>
	</div>
</template>

<script>
export default {
	name: "RequestDetail",
 	data() {
		return {
			calls: [],
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_calls",
			args: {
				uuid: this.$route.param
			}
		}).then( r => {
			this.calls = r.message
		})
	},
};
</script>
