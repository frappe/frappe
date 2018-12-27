<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>UUID</th>
				<th>CMD</th>
			</tr>
		</thead>
		<tbody>
			<tr v-for="request in requests" :key="request.uuid" v-bind="request">
				<td>
					<a :href="'#Request/' + request.uuid ">{{ request.uuid }}</a>
				</td>
				<td>
					{{ request.cmd }}
				</td>
			</tr>
		</tbody>
	</table>
</template>

<script>
export default {
	name: "PathDetail",
	data() {
		return {
			requests: [],
		};
	},
	mounted() {
		frappe.call({
			method: "frappe.www.recorder.get_requests",
			args: {
				path: this.$route.param
			}
		}).then( r => {
			this.requests = r.message
		})
	},
};
</script>
