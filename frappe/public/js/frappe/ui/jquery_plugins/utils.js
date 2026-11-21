export const is_touch_device = () => "ontouchstart" in document.documentElement;

export function get_selector(element) {
	let selector = element.getAttribute("data-target");
	if (!selector || selector === "#") {
		const href = element.getAttribute("href");
		selector = href && href !== "#" ? href.trim() : "";
	}

	try {
		return document.querySelector(selector) ? selector : null;
	} catch {
		return null;
	}
}

export function reflow(element) {
	return element.offsetHeight;
}

export function transition_duration(element) {
	if (!element) return 0;
	const style = getComputedStyle(element);
	const duration = parseFloat(style.transitionDuration) || 0;
	const delay = parseFloat(style.transitionDelay) || 0;
	return (duration + delay) * 1000;
}

export function after_transition(element, callback, duration = transition_duration(element)) {
	let timer;
	const done = (event) => {
		if (event && event.target !== element) return;
		cancel();
		callback();
	};
	const cancel = () => {
		element.removeEventListener("transitionend", done);
		clearTimeout(timer);
	};
	element.addEventListener("transitionend", done);
	timer = setTimeout(done, duration);
	return cancel;
}

export function trigger(element, name, props) {
	const event = $.Event(name, props);
	$(element).trigger(event);
	return event;
}

export function call_method(plugin, method, ...args) {
	if (typeof plugin[method] !== "function" || method.startsWith("_")) {
		throw new TypeError(`No method named "${method}"`);
	}
	return plugin[method](...args);
}
