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
			frequently_visited_list: [
				'User Permission',
				'Issues',
				'Sales Order',
				'Purchase Invoice',
			]
		}
	},
	methods: {
		goto_list(doctype) {
			frappe.set_route('List', doctype);
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

