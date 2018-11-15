import Vue from 'vue/dist/vue.js';

if (!window.Vue) {
	Vue.prototype.__ = window.__;
	Vue.prototype.frappe = window.frappe;
	window.Vue = Vue;
}
