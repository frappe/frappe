<template>
	<div>
		<component :is="current_component"/>
	</div>
</template>

<script>
import Vue from 'vue/dist/vue.js'
Vue.prototype.$route = { param: null }

import RecorderDetail from "./RecorderDetail.vue"
import PathDetail from "./PathDetail.vue"
import RequestDetail from "./RequestDetail.vue"

export default {
	name: "RecorderRoot",
	data () {
		return {
			current_component: RecorderDetail
		}
	},
	mounted () {
		this.set_component()
		window.onhashchange = this.set_component
	},
	methods: {
		set_component: function () {
			var routes = {
				"#": RecorderDetail,
				"#Path": PathDetail,
				"#Request": RequestDetail,
			}
			var route = this.get_route()
			this.$route.param = route.param
			this.current_component = routes[route.route]
		},
		get_route: function () {
			var hash = window.location.hash
			if (hash) {
				var array = hash.split("/")
				var route = array[0]
				var param = array.slice(1).join("/")
			}
			else {
				var route = "#"
				var param = ""
			}
			return { route, param }
		},
	},
};
</script>
