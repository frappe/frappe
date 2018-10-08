frappe.provide('frappe.ui');

frappe.ui.Sidebar = class Sidebar {
	constructor({ wrapper, css_class }) {
		this.wrapper = wrapper;
		this.css_class = css_class;
		this.items = {};
		this.make_dom();
	}

	make_dom() {
		this.wrapper.html(`
			<div class="${this.css_class} overlay-sidebar hidden-xs hidden-sm">
			</div>
		`);

		this.$sidebar = this.wrapper.find('.' + this.css_class);
	}

	add_item(item, section, h6=false) {
		let $section, $li_item;
		if(!section && this.wrapper.find('.sidebar-menu').length === 0) {
			// if no section, add section with no heading
			$section = this.get_section();
		} else {
			$section = this.get_section(section);
		}

		if(item instanceof jQuery) {
			$li_item = $(`<li>`);
			item.appendTo($li_item);
		} else {
			const className = h6 ? 'h6' : '';
			const html = `<li class=${className}>
				<a ${item.href ? `href="${item.href}"` : ''}>${item.label}</a>
			</li>`;
			$li_item = $(html).click(
				() => item.on_click && item.on_click()
			);
		}

		$section.append($li_item);

		if(item.name) {
			this.items[item.name] = $li_item;
		}
	}

	remove_item(name) {
		if(this.items[name]) {
			this.items[name].remove();
		}
	}

	get_section(section_heading="") {
		let $section = $(this.wrapper.find(
			`[data-section-heading="${section_heading}"]`));
		if($section.length) {
			return $section;
		}

		const $section_heading = section_heading ?
			`<li class="h6">${section_heading}</li>` : '';

		$section = $(`
			<ul class="list-unstyled sidebar-menu" data-section-heading="${section_heading || 'default'}">
				${$section_heading}
			</ul>
		`);

		this.$sidebar.append($section);
		return $section;
	}
};
