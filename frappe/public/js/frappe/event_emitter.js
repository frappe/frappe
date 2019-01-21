frappe.provide('frappe.utils');
/**
 * Simple EventEmitterMixin which uses jQuery's event system
 */
const EventEmitterMixin = {
	init() {
		this.jq = jQuery({});
	},

	trigger(evt, data) {
		!this.jq && this.init();
		this.jq.trigger(evt, data);
	},

	once(evt, handler) {
		!this.jq && this.init();
		this.jq.one(evt, (e, data) => handler(data));
	},

	on(evt, handler) {
		!this.jq && this.init();
		this.jq.bind(evt, (e, data) => handler(data));
	},

	off(evt, handler) {
		!this.jq && this.init();
		this.jq.unbind(evt, (e, data) => handler(data));
	}
}

frappe.utils.make_event_emitter = function(object) {
	Object.assign(object, EventEmitterMixin);
	return object;
};

export default EventEmitterMixin;
