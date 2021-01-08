frappe.ui.form.ControlRating  = frappe.ui.form.ControlInt.extend({
	make_input() {
		this._super();
		const star_template = `
			<div class="rating">
				<i class="fa fa-fw fa-star" data-rating=1></i>
				<i class="fa fa-fw fa-star" data-rating=2></i>
				<i class="fa fa-fw fa-star" data-rating=3></i>
				<i class="fa fa-fw fa-star" data-rating=4></i>
				<i class="fa fa-fw fa-star" data-rating=5></i>
			</div>
		`;

		$(this.input_area).html(star_template);

		$(this.input_area).find('i').hover((ev) => {
			const el = $(ev.currentTarget);
			let star_value = el.data('rating');
			el.parent().children('i.fa').each( function(e) {
				if (e < star_value) {
					$(this).addClass('star-hover');
				} else {
					$(this).removeClass('star-hover');
				}
			});
		}, (ev) => {
			const el = $(ev.currentTarget);
			el.parent().children('i.fa').each( function() {
				$(this).removeClass('star-hover');
			});
		});

		$(this.input_area).find('i').click((ev) => {
			const el = $(ev.currentTarget);
			let star_value = el.data('rating');
			el.parent().children('i.fa').each( function(e) {
				if (e < star_value){
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
		let el = $(this.input_area).find('i');
		el.children('i.fa').prevObject.each( function(e) {
			if (e < value) {
				$(this).addClass('star-click');
			} else {
				$(this).removeClass('star-click');
			}
		});
	}
});