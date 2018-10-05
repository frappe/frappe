<template>
	<div class="flex flex-column">
		<p><label class="label label-warning" title="This feature is brand new and still experimental">Under Development</label></p>
		<div class="muted-title">
			Frequently Visited Links
		</div>
		<div class="flex flex-column">
			<a @click.prevent="goto_list(route_obj.route)" v-for="route_obj in frequently_visited_list" :key="route_obj.route">{{route_obj.route}}</a>
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
		goto_list(route) {
			frappe.set_route(route);
		},
		set_frequently_visited_list() {
			frappe.xcall('frappe.social.doctype.post.post.frequently_visited_links').then(data => {
				this.frequently_visited_list = data;
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

