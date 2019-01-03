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
			<tr v-for="call in calls" :key="call.index" v-bind="call">
				<td>
					<router-link :to="{name: 'sql-detail', params: {call_index: call.index}} ">{{ call.index }}</router-link>
				</td>
				<td>
					{{ call.query }}
				</td>
				<td>
					{{ call.time.start }}
				</td>
				<td>
					{{ call.time.total }}
				</td>
			</tr>
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
			this.calls = r.message.calls
		})
	},
};
</script>
