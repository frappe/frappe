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

		this.form = this.wrapper.find("form").on("submit", function () {
			return false;
		});

		if (this.df.label) {
			$(`
				<label class="control-label">
					${__(this.df.label)}
				</label>
			`).appendTo(this.wrapper);
		}
	}

	resize_all_columns() {
		// distribute all columns equally
		let colspan = cint(12 / this.section.wrapper.find(".form-column").length);

		this.section.wrapper
			.find(".form-column")
			.removeClass()
			.addClass("form-column")
			.addClass("col-sm-" + colspan);
	}

	add_field() {}

	refresh() {
		this.section.refresh();
	}

	make_sortable() {
		this.sortable = new Sortable(this.form.get(0), {
			group: this.section.layout.frm.doctype,
		});
	}
}
