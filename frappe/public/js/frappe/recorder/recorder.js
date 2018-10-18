import Vue from 'vue/dist/vue.js';
import Recorder from "./Recorder.vue";

new Vue({
	el: "#recorder",
	template: "<recorder-app/>",
	components: { recorderApp: Recorder }
});
