export default class Widget {
	constructor(opts) {
		Object.assign(this, opts);
		this.make_widget();
		this.setup_events();
	}
}