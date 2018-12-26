<template>
	<table class="table table-hover">
		<thead>
			<tr>
				<th>UUID</th>
				<th>CMD</th>
			</tr>
		</thead>
		<tbody>
			<request-list-item v-for="request in requests" :key="request.uuid" v-bind="request"/>
		</tbody>
	</table>
</template>

<script>
import RequestListItem from "./RequestListItem.vue"
export default {
	name: "RequestList",
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
	components: {
		RequestListItem,
	}
};
</script>
