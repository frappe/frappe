<template>
	<div class="flex flex-column">
		<p><label class="label label-warning" title="This feature is brand new and still experimental">Under Development</label></p>
		<div class="muted-title">
			Frequently Visited Links
		</div>
		<div class="flex flex-column">
			<a @click.prevent="goto_list(doctype)" v-for="doctype in frequently_visited_list" :key="doctype">{{doctype}}</a>
		</div>
	</div>
</template>
<script>
export default {
	props: ['user'],
	data() {
		return {
			frequently_visited_list: []
		}
	},
	created() {
		this.set_frequently_visited_list()
	},
	methods: {
		goto_list(doctype) {
			frappe.set_route('List', doctype);
		},
		set_frequently_visited_list() {
			frappe.model.user_settings.get('Route').then(data => {
				let obj = {}
				let route_history = data.route_history || ''
				route_history = data.route_history.split('\n');
				route_history.forEach(element => {
					if (element === "") return
					if (!obj[element]) {
						obj[element] = 1;
					} else {
						obj[element]++;
					}
				});
				let list = Object.keys(obj).sort((a, b) => {
					return obj[b] - obj[a];
				});
				this.frequently_visited_list = list;
			})
		}
	}
}
</script>
<style lang="less" scoped>
a {
	margin: 10px;
}
.stats {
	min-height: 150px
}
</style>

