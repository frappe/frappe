import BaseAwesomplete from "awesomplete";

export default class Awesomplete extends BaseAwesomplete {
	constructor(input, options) {
		super(input, options);
		this.status.textContent = this.minChars
			? __("Type {0} or more characters for results.", [this.minChars])
			: __("Begin typing for results.");
	}

	evaluate() {
		super.evaluate();
		this.status.textContent = this.opened
			? __("{0} results found", [this.ul.children.length])
			: __("No results found");
	}

	goto(index) {
		super.goto(index);
		const items = this.ul.children;
		if (index > -1 && items.length) {
			this.status.textContent = __("{0}, list item {1} of {2}", [
				items[index].textContent,
				index + 1,
				items.length,
			]);
		}
	}
}

// replace the global set by the library, so consumers outside this bundle
// (awesome bar, tag editor, field select) get this subclass without
// bundling their own copy of the library
if (typeof window !== "undefined") {
	window.Awesomplete = Awesomplete;
}
