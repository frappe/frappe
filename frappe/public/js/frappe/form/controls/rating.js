frappe.ui.form.ControlRating  = frappe.ui.form.ControlInt.extend({
	make_input() {
		this._super();
		let stars = '';
		[1, 2, 3, 4, 5].forEach(i => {
			stars += `<svg class="icon icon-md" data-rating=${i}>
				<use href="#icon-star"></use>
			</svg>`;
		});
		const star_template = `
			<div class="rating">
				${stars}
			</div>
		`;

		$(this.input_area).html(star_template);

		$(this.input_area).find('svg').hover((ev) => {
			const el = $(ev.currentTarget);
			let star_value = el.data('rating');
			el.parent().children('svg').each( function(e) {
				if (e < star_value) {
					$(this).addClass('star-hover');
				} else {
					$(this).removeClass('star-hover');
				}
			});
		}, (ev) => {
			const el = $(ev.currentTarget);
			el.parent().children('svg').each( function() {
				$(this).removeClass('star-hover');
			});
		});

		$(this.input_area).find('svg').click((ev) => {
			const el = $(ev.currentTarget);
			let star_value = el.data('rating');
			el.parent().children('svg').each( function(e) {
				if (e < star_value) {
					$(this).addClass('star-click');
				} else {
					$(this).removeClass('star-click');
				}
			});
			this.validate_and_set_in_model(star_value, ev);
			if (this.doctype && this.docname) {
				this.set_input(star_value);
			}
		});
	},
	get_value() {
		return cint(this.value, null);
	},
	set_formatted_input(value) {
		let el = $(this.input_area).find('svg');
		el.children('svg').prevObject.each( function(e) {
			if (e < value) {
				$(this).addClass('star-click');
			} else {
				$(this).removeClass('star-click');
			}
		});
	}
});
