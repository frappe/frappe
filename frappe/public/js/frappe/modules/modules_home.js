import Modules from './Modules.vue';

frappe.provide('frappe.modules');

frappe.modules.Home = class {
	constructor({ parent }) {
		this.$parent = $(parent);
		this.page = parent.page;
		this.setup_header();
		this.make_body();
	}
	make_body() {
		this.$modules_container = this.$parent.find('.layout-main');
		frappe.require('/assets/js/frappe-vue.min.js', () => {
			Vue.prototype.__ = window.__; 
			new Vue({
				el: this.$modules_container[0],
				render: h => h(Modules)
			});
		});
	}
	setup_header() {
		this.page.set_title(__('Modules'));
	}
};
