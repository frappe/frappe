<template>
	<div>
		<ol>
			<li v-for="request in requests" :key="request.uuid">
				<request-list-item v-bind="request"/>
			</li>
		</ol>
	</div>
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
