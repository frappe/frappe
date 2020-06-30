// Copyright (c) 2018, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt
frappe.provide('frappe.ui.form');

frappe.ui.form.Selector = class Selector {
	constructor() {}

	get_filters (doctype, setters) {
		/**
		 * Return 3 column formatted filters for Dialog
		 */

		let fields = [];
		let columns = new Array(3);

		// Hack for three column layout
		// To add column break
		columns[0] = [
			{
				fieldtype: "Data",
				label: __("Search"),
				fieldname: "search_term",
				description: __("You can use wildcard %")
			}
		];
		columns[1] = [];
		columns[2] = [];

		Object.keys(setters).forEach((setter, index) => {
			let df_prop = frappe.meta.docfield_map[doctype][setter];

			// Index + 1 to start filling from index 1
			// Since Search is a standrd field already pushed
			columns[(index + 1) % 3].push({
				fieldtype: df_prop.fieldtype,
				label: df_prop.label,
				fieldname: setter,
				options: df_prop.options,
				default: setters[setter]
			});
		});

		// https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Global_Objects/Object/seal
		if (Object.seal) {
			Object.seal(columns);
			// now a is a fixed-size array with mutable entries
		}

		fields = [
			...columns[0],
			{ fieldtype: "Column Break" },
			...columns[1],
			{ fieldtype: "Column Break" },
			...columns[2],
			{ fieldtype: "Section Break", fieldname: "primary_filters_sb" }
		];

		return fields;
	}

	make_list_row (doctype, setters, result={}) {
		/**
		 * Formats result in List View
		 */

		// Make a head row by default (if result not passed)
		let head = Object.keys(result).length === 0;

		let contents = ``;
		let columns = ["name"];

		columns = columns.concat(Object.keys(setters));

		columns.forEach(function (column) {
			contents += `<div class="list-item__content ellipsis">
				${
	head ? `<span class="ellipsis text-muted" title="${__(frappe.model.unscrub(column))}">${__(frappe.model.unscrub(column))}</span>`
		: (column !== "name" ? `<span class="ellipsis result-row" title="${__(result[column] || '')}">${__(result[column] || '')}</span>`
			: `<a href="${"#Form/" + doctype + "/" + result[column] || ''}" class="list-id ellipsis" title="${__(result[column] || '')}">
							${__(result[column] || '')}</a>`)}
			</div>`;
		});

		let $row = $(`<div class="list-item">
			<div class="list-item__content" style="flex: 0 0 10px;">
				<input type="checkbox" class="list-row-check" data-item-name="${result.name}" ${result.checked ? 'checked' : ''}>
			</div>
			${contents}
		</div>`);

		head ? $row.addClass('list-item--head')
			: $row = $(`<div class="list-item-container" data-item-name="${result.name}"></div>`).append($row);

		$(".modal-dialog .list-item--head").css("z-index", 0);
		return $row;
	}

	make_card (columns, result={}) {
		/**
		 * Formats result in Card View
		 */
		return $(`<div class="grid-item">
				${ this.get_image_html(result["image"], result["name"]) }
				<div class="round">
   					 <input class="Check" type="checkbox" data-name="${result["name"]}"/>
  				</div>
				<div style="text-align: left;">
					<div class= "card-content">${frappe.ellipsis(result["name"], 20)}</div>
					<div class="card-content-muted">${frappe.ellipsis(result[columns[1]], 18)}</div>
					<div class="card-content-muted">${frappe.ellipsis(result[columns[2]], 18)}</div>
				</div>
				</div>`);
	}

	get_image_html (image, name) {
		if (image) {
			return `<img class= "thumb" src=${image} alt=${name} title=${name}>
				</img>`;
		} else {
			return `<div class="thumb" style="background-color: #fafbfc;">
				<span style="color:#d1d8dd; font-size:48px; margin-top: 20px;">${frappe.get_abbr(name)}</span>
				</div>`;
		}

	}
};