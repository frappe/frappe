<template>
	<div>
		<div id="accordion-sql">
			<div v-for="call in calls" :key="call.index" class="card">
				<div class="card-header" :id="'heading-sql-' + call.index ">
					<h5 class="mb-0">
						<button class="btn btn-link" data-toggle="collapse" :data-target="'#collapse-sql-' + call.index ">
							{{ call.query }}
							{{ call.time.total }}
						</button>
					</h5>
				</div>
				<div :id="'collapse-sql-' + call.index " class="collapse" data-parent="#accordion-sql">
					<div class="card-body">
						<div><pre>{{ call.stack }}</pre></div>
						<div><pre>{{ call.query }}</pre></div>
					</div>
				</div>
			</div>
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
