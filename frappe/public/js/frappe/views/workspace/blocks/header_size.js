export default class HeaderSize {
	static get isInline() {
		return true;
	}

	get state() {
		return this._state;
	}

	set state(state) {
		this._state = state;
	}

	get title() {
		return "Header Size";
	}

	constructor({ api }) {
		this.api = api;
		this.button = null;
		this._state = true;
		this.selectedText = null;
		this.range = null;
		this.headerLevels = [];
	}

	render() {
		this.button = document.createElement("button");
		this.button.type = "button";
		this.button.innerHTML = `${frappe.utils.icon("header", "sm")}${frappe.utils.icon(
			"small-down",
			"xs"
		)}`;
		this.button.classList = "header-inline-tool";

		return this.button;
	}

	checkState(selection) {
		let termWrapper = this.api.selection.findParentTag("SPAN");

		for (const h of ["h1", "h2", "h3", "h4", "h5", "h6"]) {
			if (termWrapper && termWrapper.classList.contains(h)) {
				let num = h.match(/\d+/)[0];
				$(".header-inline-tool svg:first-child").replaceWith(
					frappe.utils.icon(`header-${num}`, "md")
				);
			}
		}

		const text = selection.anchorNode;
		if (!text) return;
	}

	change_size(range, size) {
		if (!range) return;

		let span = document.createElement("SPAN");

		span.classList.add(`h${size}`);
		span.innerText = range.toString();

		this.remove_parent_tag(range, range.commonAncestorContainer, span);

		range.extractContents();
		range.insertNode(span);
		this.api.inlineToolbar.close();
	}

	remove_parent_tag(range, parent_node, span) {
		let diff = range.startContainer.data;
		let selected_text = span.innerText;
		let parent_tag = parent_node.parentElement;

		if (diff !== selected_text) {
			parent_tag = parent_node;
		}

		if (parent_tag.innerText == selected_text) {
			if (
				!parent_tag.classList.contains("ce-header") &&
				!parent_tag.classList.contains("ce-paragraph")
			) {
				this.remove_parent_tag(range, parent_node.parentElement, span);
				parent_tag.remove();
			}
		}
	}

	surround(range) {
		this.selectedText = range.cloneContents();
		this.actions.hidden = !this.actions.hidden;
		this.range = !this.actions.hidden ? range : null;
		this.state = !this.actions.hidden;
	}

	renderActions() {
		this.actions = document.createElement("div");
		this.actions.classList = "header-level-select";

		this.headerLevels = new Array(6).fill().map((_, idx) => {
			const $header_level = document.createElement("div");
			$header_level.classList.add(`h${idx + 1}`, "header-level");
			$header_level.innerText = `Header ${idx + 1}`;
			return $header_level;
		});

		for (const [i, headerLevel] of this.headerLevels.entries()) {
			this.actions.appendChild(headerLevel);
			this.api.listeners.on(headerLevel, "click", () => {
				this.change_size(this.range, i + 1);
			});
		}

		this.actions.hidden = true;
		return this.actions;
	}

	destroy() {
		for (const headerLevel of this.headerLevels) {
			this.api.listeners.off(headerLevel, "click");
		}
	}
}
