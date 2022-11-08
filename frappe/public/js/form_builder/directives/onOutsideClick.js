const instanceMap = new Map();

function onDocumentClick(e, el, fn) {
	let target = e.target;
	if (el !== target && !el.contains(target)) {
		fn?.(e);
	}
}

export default {
	beforeMount(el, binding) {
		const fn = binding.value;
		const clickHandler = function (e) {
			onDocumentClick(e, el, fn);
		};

		removeHandlerIfPresent(el);
		instanceMap.set(el, clickHandler);
		document.addEventListener("click", clickHandler);
	},
	unmounted(el) {
		removeHandlerIfPresent(el);
	},
};

function removeHandlerIfPresent(el) {
	const clickHandler = instanceMap.get(el);
	if (!clickHandler) {
		return;
	}

	instanceMap.delete(el);
	document.removeEventListener("click", clickHandler);
}
