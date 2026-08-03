// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.Tags = class {
	constructor({ parent, placeholder, tagsList, onTagAdd, onTagRemove, onTagClick, onChange }) {
		this.tagsList = tagsList || [];
		this.onTagAdd = onTagAdd;
		this.onTagRemove = onTagRemove;
		this.onTagClick = onTagClick;
		this.onChange = onChange;

		this.setup(parent, placeholder);
	}

	setup(parent, placeholder) {
		this.$ul = parent;
		this.$input = $(`<input class="tags-input form-control mt-2"></input>`);

		this.$inputWrapper = this.get_list_element(this.$input);
		this.$placeholder =
			$(`<button type="button" class="es-button add-tags-btn" data-variant="ghost" data-icon-button="true" title="${__(
				"Add Tags"
			)}" aria-label="${__("Add Tags")}">
				${__(placeholder)}
			</button>`);
		this.$placeholder.appendTo(this.$ul.find(".form-sidebar-items"));
		this.$inputWrapper.appendTo(this.$ul);

		this.deactivate();
		this.bind();
		this.boot();
	}

	bind() {
		const me = this;
		const select_tag = function () {
			const tagValue = frappe.utils.xss_sanitise(me.$input.val());
			me.addTag(tagValue);
			me.$input.val("");
		};

		const activate_input = () => {
			this.activate();
			this.$input.focus();
		};

		this.$input.keypress((e) => {
			if (e.which == 13 || e.keyCode == 13) {
				// Triggers event when <enter> is pressed
				this.$input.trigger("enter-pressed-in-addtag");
			}
		});
		this.$input.focusout(select_tag);

		this.$input.on("input-selected", () => {
			// Adds tag if a input is selected
			select_tag();
			this.deactivate();
		});

		this.$input.on("blur", () => {
			this.deactivate();
		});

		this.$placeholder.on("click", activate_input);
		this.$ul.find(".tags-label").on("click", activate_input);
	}

	boot() {
		this.addTags(this.tagsList);
	}

	activate() {
		this.$placeholder.hide();
		this.$inputWrapper.show();
	}

	deactivate() {
		this.$inputWrapper.hide();
		this.$placeholder.show();
	}

	addTag(label) {
		if (label && label !== "" && !this.tagsList.includes(label)) {
			let $tag = this.get_tag(label);
			let row = this.get_list_element($tag, "form-tag-row");
			row.insertAfter(this.$inputWrapper);
			this.tagsList.push(label);
			this.onTagAdd && this.onTagAdd(label);
		}
	}

	removeTag(label) {
		label = frappe.utils.xss_sanitise(label);
		if (this.tagsList.includes(label)) {
			this.tagsList.splice(this.tagsList.indexOf(label), 1);
			this.onTagRemove && this.onTagRemove(label);
		}
	}

	addTags(labels) {
		labels.map(this.addTag.bind(this));
	}

	clearTags() {
		this.$ul.find(".form-tag-row").remove();
		this.tagsList = [];
	}

	get_list_element($element, class_name = "") {
		let $li = $(`<div class="${class_name}"></div>`);
		$element.appendTo($li);
		return $li;
	}

	get_tag(label) {
		let $tag = frappe.ui.badge({
			label: label,
			theme: this.get_tag_theme(label),
			size: "lg",
			icon_right: "x",
			css_class: "form-tag",
			title: label,
		});

		// wrap the label text so truncation can engage (a bare text node in a
		// flex container can't ellipsize); also the onTagClick target
		$tag.contents()
			.filter((_, node) => node.nodeType === Node.TEXT_NODE && node.textContent.trim())
			.wrap('<span class="pill-label ellipsis"></span>');

		// the ✕ is the only click target — the badge itself stays inert
		const $remove = $tag.find(".es-badge__affix");
		$remove
			.attr({ role: "button", tabindex: 0, "aria-label": __("Remove") })
			.on("click", () => {
				this.removeTag(label);
				$tag.closest(".form-tag-row").remove();
			})
			.on("keydown", (e) => {
				if (e.key === "Enter" || e.key === " ") {
					e.preventDefault();
					$remove.trigger("click");
				}
			});

		if (this.onTagClick) {
			$tag.on("click", ".pill-label", () => {
				this.onTagClick(label);
			});
		}
		return $tag;
	}

	get_tag_theme(label) {
		// same tag → same color, spread over the badge's curated themes
		const themes = ["blue", "green", "amber", "red", "violet"];
		let hash = 0;
		for (let i = 0; i < label.length; i++) {
			hash = (hash * 31 + label.charCodeAt(i)) % 997;
		}
		return themes[hash % themes.length];
	}
};
