frappe.ui.form.ControlRating = class ControlRating extends frappe.ui.form.ControlInt {
	make_input() {
		super.make_input();
		let stars = '';
		let number_of_stars = this.df.options || 5;
		Array.from({length: cint(number_of_stars)}, (_, i) => i + 1).forEach(i => {
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
			let out_of_ratings = this.df.options || 5;

			star_value = star_value/out_of_ratings;
			this.validate_and_set_in_model(star_value, ev);
			if (this.doctype && this.docname) {
				this.set_input(star_value);
			}
		});
	}
	get_value() {
		let out_of_ratings = this.df.options || 5;
		return cint(this.value*out_of_ratings, null);
	}
	set_formatted_input(value) {
		let out_of_ratings = this.df.options || 5;
		value = value * out_of_ratings;
		let el = $(this.input_area).find('svg');
		el.children('svg').prevObject.each( function(e) {
			if (e < value) {
				$(this).addClass('star-click');
			} else {
				$(this).removeClass('star-click');
			}
		});
	}
	validate(fraction) {
		return parseFloat(fraction);
	}
};
