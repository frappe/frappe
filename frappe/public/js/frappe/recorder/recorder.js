import Vue from 'vue/dist/vue.js'
import Recorder from "./Recorder.vue"

frappe.ready(function() {
	new Vue({
		el: "#recorder",
		template: "<recorder-app/>",
		components: { recorderApp: Recorder }
	})
})
