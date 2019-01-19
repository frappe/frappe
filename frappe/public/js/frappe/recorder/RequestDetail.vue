<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>Index</th>
				<th>Query</th>
				<th>Time</th>
				<th>Execution Time</th>
			</tr>
		</thead>
		<tbody>
			<router-link style="cursor: pointer" :to="{name: 'sql-detail', params: {call_index: call.index}}" tag="tr" v-for="call in calls" :key="call.index" v-bind="call">
				<td>{{ call.index }}</td>
				<td>{{ call.query }}</td>
				<td>{{ call.time.start }}</td>
				<td>{{ call.time.total }}</td>
			</router-link>
		</tbody>
	</table>

</template>

<script>
export default {
	name: "RequestDetail",
 	data() {
		return {
			cache: [],
			calls: [],
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_request_data",
			args: {
				uuid: this.$route.params.request_uuid
			}
		}).then( r => {
			this.calls = r.message.calls;
		});
	},
};
</script>
