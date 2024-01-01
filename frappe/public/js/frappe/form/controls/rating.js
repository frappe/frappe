frappe.ui.form.ControlRating = class ControlRating extends frappe.ui.form.ControlFloat {
	make_input() {
		super.make_input();
		let stars = "";
		let number_of_stars = this.df.options || 5;
		Array.from({ length: cint(number_of_stars) }, (_, i) => i + 1).forEach((i) => {
			stars += `<svg class="icon icon-md" data-rating=${i} viewBox="0 0 24 24" fill="none">
				<path class="right-half" d="M11.9987 3.00011C12.177 3.00011 12.3554 3.09303 12.4471 3.27888L14.8213 8.09112C14.8941 8.23872 15.0349 8.34102 15.1978 8.3647L20.5069 9.13641C20.917 9.19602 21.0807 9.69992 20.7841 9.9892L16.9421 13.7354C16.8243 13.8503 16.7706 14.0157 16.7984 14.1779L17.7053 19.4674C17.7753 19.8759 17.3466 20.1874 16.9798 19.9945L12.2314 17.4973C12.1586 17.459 12.0786 17.4398 11.9987 17.4398V3.00011Z" fill="var(--star-fill)" stroke="var(--star-fill)"/>
				<path class="left-half" d="M11.9987 3.00011C11.8207 3.00011 11.6428 3.09261 11.5509 3.27762L9.15562 8.09836C9.08253 8.24546 8.94185 8.34728 8.77927 8.37075L3.42887 9.14298C3.01771 9.20233 2.85405 9.70811 3.1525 9.99707L7.01978 13.7414C7.13858 13.8564 7.19283 14.0228 7.16469 14.1857L6.25116 19.4762C6.18071 19.8842 6.6083 20.1961 6.97531 20.0045L11.7672 17.5022C11.8397 17.4643 11.9192 17.4454 11.9987 17.4454V3.00011Z" fill="var(--star-fill)" stroke="var(--star-fill)"/>
			</svg>`;
		});

		const star_template = `
			<div class="rating">
				${stars}
			</div>
		`;

		$(this.input_area).html(star_template);

		let me = this;
		$(this.input_area)
			.find("svg")
			.on("mousemove", function (ev) {
				me.update_rating(ev);
			})
			.on("mouseout", function (ev) {
				const el = $(ev.currentTarget);
				el.parent()
					.children("svg")
					.each(function () {
						$(this).find(".left-half, .right-half").removeClass("star-hover");
					});
			});

		$(this.input_area)
			.find("svg")
			.click((ev) => {
				this.update_rating(ev, true);
			});
	}

	update_rating(ev, click) {
		const el = $(ev.currentTarget);
		let star_value = el.data("rating");
		let left_half = false;
		let cls = "star-click";
		if (!click) cls = "star-hover";

		if (ev.pageX - el.offset().left < el.width() / 2) {
			left_half = true;
			star_value--;
		}
		el.parent()
			.children("svg")
			.each(function (e) {
				if (e < star_value) {
					$(this).find(".left-half, .right-half").addClass(cls);
				} else if (e == star_value && left_half) {
					$(this).find(".left-half").addClass(cls);
					$(this).find(".right-half").removeClass(cls);
					if (click) star_value += 0.5;
				} else {
					$(this).find(".left-half, .right-half").removeClass(cls);
				}
			});
		if (click) {
			let out_of_ratings = this.df.options || 5;
			star_value = star_value / out_of_ratings;

			this.validate_and_set_in_model(star_value, ev);
			if (this.doctype && this.docname) {
				this.set_input(star_value);
			}
		}
	}

	get_value() {
		return this.value;
	}
	set_formatted_input(value) {
		let out_of_ratings = this.df.options || 5;
		value = value * out_of_ratings;
		value = Math.round(value * 2) / 2; // roundoff number to nearest 0.5
		let el = $(this.input_area).find("svg");
		el.children("svg").prevObject.each(function (e) {
			if (e < value) {
				$(this).find(".left-half, .right-half").addClass("star-click");

				let is_half = e == Math.floor(value) && value % 1 == 0.5;
				is_half && $(this).find(".right-half").removeClass("star-click");
			} else {
				$(this).find(".left-half, .right-half").removeClass("star-click");
			}
		});
	}
	validate(fraction) {
		return parseFloat(fraction);
	}
};
