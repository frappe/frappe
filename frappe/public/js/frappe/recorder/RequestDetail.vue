<template>
	<div>
		<div id="accordion-sql">
			<div v-for="call in calls" :key="call.index" class="card">
				<div class="card-header" :id="'heading-' + call.index ">
					<h5 class="mb-0">
						<button class="btn btn-link" data-toggle="collapse" :data-target="'#collapse-' + call.index ">
							{{ call.query }}
							{{ call.time.total }}
						</button>
					</h5>
				</div>
				<div :id="'collapse-' + call.index " class="collapse" data-parent="#accordion-sql">
					<div class="card-body">
						<div><pre>{{ call.stack }}</pre></div>
						<div><pre>{{ call.query }}</pre></div>
					</div>
				</div>
			</div>
		</div>

		<div id="accordion-cache">
			<div v-for="call in cache" :key="call.index" class="card">
				<div class="card-header" :id="'heading-' + call.index ">
					<h5 class="mb-0">
						<button class="btn btn-link" data-toggle="collapse" :data-target="'#collapse-' + call.index ">
							{{ call.call }}
							{{ call.time.total }}
						</button>
					</h5>
				</div>
				<div :id="'collapse-' + call.index " class="collapse" data-parent="#accordion-cache">
					<div class="card-body">
						<div><pre>{{ call.stack }}</pre></div>
						<div><pre>{{ call.call }}</pre></div>
					</div>
				</div>
			</div>
		</div>


		<div>
			<div v-for="stat in stats" :key="stat.name">
				{{ stat }}<br/>
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
