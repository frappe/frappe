import Vue from 'vue/dist/vue.js'
import RecorderRoot from "./RecorderRoot.vue"

frappe.ready(function() {
	new Vue({
		el: "#recorder",
		template: "<recorder-root/>",
		components: {
			RecorderRoot,
		}
	})
})
