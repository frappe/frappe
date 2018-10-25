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
			cache: [],
			calls: [],
			stats: [],
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_request_data",
			args: {
				uuid: this.$route.param
			}
		}).then( r => {
			this.cache = r.message.cache
			this.calls = r.message.calls
			this.stats = r.message.stats
		})
	},
};
</script>
