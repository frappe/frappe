export default class Column {
	constructor(section, df) {
		if (!df) df = {};

		this.df = df;
		this.section = section;
		this.section.columns.push(this);
		this.make();
		this.resize_all_columns();
	}

	make() {
		this.wrapper = $(`
			<div class="form-column" data-fieldname="${this.df.fieldname}">
				<form>
				</form>
			</div>
		`).appendTo(this.section.body);

		this.form = this.wrapper.find("form").on("submit", () => false);

		if (this.df.description) {
			$(`
				<p class="col-sm-12 form-column-description">
					${__(this.df.description, null, this.df.parent)}
				</p>
			`).prependTo(this.wrapper);
		}

		if (this.df.label) {
			$(`
				<label class="column-label">
					${__(this.df.label, null, this.df.parent)}
				</label>
			`).prependTo(this.wrapper);
		}
	}

	resize_all_columns() {
		// distribute visible columns equally, scoped to this section's direct children only
		let all_columns = this.section.body.children(".form-column");
		let visible_columns = all_columns.filter(":not(.hide-control)");
		let columns = visible_columns.length || all_columns.length;
		let colspan = cint(12 / columns);

		if (columns == 5) {
			colspan = 20;
		}

		all_columns.each(function () {
			const $col = $(this);
			const is_hidden = $col.hasClass("hide-control");
			$col.removeClass()
				.addClass("form-column")
				.addClass("col-sm-" + colspan);
			if (is_hidden) {
				$col.addClass("hide-control");
			}
		});
	}

	add_field() {}

	refresh() {
		if (!this.df) return;
		const hide = this.df.hidden || this.df.hidden_due_to_dependency;
		this.wrapper.toggleClass("hide-control", !!hide);
		this.resize_all_columns();
		this.section.refresh();
	}
}
