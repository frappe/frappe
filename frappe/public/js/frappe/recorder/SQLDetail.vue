<template>
	<div>
		<div>{{ call.time.start }}</div>
		<div>{{ call.time.end }}</div>
		<div>{{ call.time.total }}</div>
		<div v-html="call.highlighted_query"></div>
		<div><pre>{{ call.stack }}</pre></div>
	</div>
</template>

<script>
export default {
	name: "SQLDetail",
 	data() {
		return {
			call: null,
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_request_data",
			args: {
				uuid: this.$route.params.request_uuid
			}
		}).then( r => {
			this.call = r.message.calls[this.$route.params.call_index]
		})
	},
};
</script>
