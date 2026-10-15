// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.ui.Tags = class {
	constructor({
		parent,
		placeholder,
		tagsList,
		onTagAdd,
		onTagRemove,
		onTagClick,
		onChange,
		get_options,
	}) {
		this.tagsList = tagsList || [];
		// (txt) => tags to pick from, in a frappe.ui.Combobox instead of the inline input
		this.get_options = get_options;
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
		if (this.get_options) {
			this.make_picker(this.$placeholder);
			return;
		}

		const me = this;
		const select_tag = function () {
			me.select(me.$input.val());
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

	select(label) {
		if (!this.has_tag(label)) this.addTag(frappe.utils.xss_sanitise(label));
	}

	has_tag(label) {
		const key = frappe.utils.xss_sanitise(label).toLowerCase();
		return this.tagsList.some((tag) => tag.toLowerCase() === key);
	}

	make_picker($trigger) {
		return new frappe.ui.Combobox({
			trigger: $trigger,
			placeholder: __("Add a tag"),
			allow_create: (txt) => !this.has_tag(txt),
			create_label: (txt) => __('Create tag "{0}"', [txt]),
			empty_text: __("No tags yet"),
			options: async (txt) =>
				(await this.get_options(txt)).filter((tag) => !this.has_tag(tag)),
			on_select: (tag) => this.select(tag),
		});
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
		let $tag = frappe.ui.tag({
			label: label,
			theme: this.get_tag_theme(label),
			removable: true,
			css_class: "form-tag",
			title: label,
		});

		$tag.find(".es-tag__label").addClass("pill-label");

		$tag.find(".es-tag__remove").on("click", () => {
			this.removeTag(label);
			$tag.closest(".form-tag-row").remove();
		});

		if (this.onTagClick) {
			$tag.on("click", ".pill-label", () => {
				this.onTagClick(label);
			});
		}
		return $tag;
	}

	get_tag_theme(label) {
		// same tag → same color, spread over the tag's themes
		const themes = ["blue", "green", "amber", "red", "violet"];
		let hash = 0;
		for (let i = 0; i < label.length; i++) {
			hash = (hash * 31 + label.charCodeAt(i)) % 997;
		}
		return themes[hash % themes.length];
	}
};
