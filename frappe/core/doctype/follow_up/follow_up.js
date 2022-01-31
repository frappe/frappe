// Copyright (c) 2022, Frappe Technologies and contributors
// For license information, please see license.txt

frappe.ui.form.on('Follow Up', {
	refresh: function (frm) {
		// document.getElementsByClassName("btn btn-xs btn-default input-sm").style.backgroundColor ='#0f81f2';
		// document.getElementByClass("btn btn-xs btn-default input-sm").style.background-color='#44bef2';

		//  frm.get_field("items").grid.cannot_add_rows = true;
		// frm.fields_dict["items"].grid.wrapper.find('.grid-add-row').hide();
		// frm.fields_dict["items"].grid.wrapper.find('.grid-remove-rows').hide();
		// $(".grid-add-row").hide();
		// frm.set_df_property("items", 'cannot_add_rows', true)
	},

	// onload_post_render: function (frm){
	// 	// $(".grid-add-row").hide();
	// },

	setup: function(frm) {
		// frm.get_field("action").$input.addClass("btn-primary");
		// to hide romove Add Row button
		frm.set_df_property("items", 'cannot_add_rows', true)
		frm.set_df_property("items", 'cannot_delete_rows', true)


	},

	get_follow_up_details: function (frm) {
		frm.clear_table("items");
		frappe.call({
			doc: frm.doc,
			method: 'get_follow_up',
			callback: function (r) {
				if (r.message) {
					console.log(" This is get count", r.message)
					frm.refresh_field("items")
				}
			}

		})
		// document.querySelectorAll("[data-fieldname='action']")[1].style.backgroundColor ="red";

	},

});

frappe.ui.form.on("Follow Up Item", {
	// onload_post_render: function(frm, cdt, cdn) {
	// 	locals[cdt][cdn].get_field("action").$input.addClass("btn-primary");
	// },

	

	action: function (frm, cdt, cdn) {
		var child = locals[cdt][cdn];
		console.log("customer",child.customer)
		frm.call({
			doc: frm.doc,
			method: 'get_accounts',
			args: {
				name :  child.customer,
			},
			callback: function (r) {
				if (r.message) {
					console.log(" This is get count", r.message)

		// creation of unique button list
		var buttons  = []
		r.message.forEach(d => { 
			buttons.push(d.follow_up)
		});
		
		var unique = [...new Set(buttons)]
		
		const cannot_add_row = (typeof false === 'undefined') ? true : false;
		const child_docname = (typeof false === 'undefined') ? "items" : "items";

		this.data = [];
		const fields = [
			{
				fieldtype: 'Link',
				fieldname: "voucher_type",
				read_only: 1,
				in_list_view: 1,
				options: "DocType",
				columns: 1,
				label: __('Voucher Type')
			},
			{
				fieldtype: 'Dynamic Link',
				fieldname: "voucher_no",
				options: 'voucher_type',
				in_list_view: 1,
				read_only: 1,
				columns: 1,
				label: __('Voucher No')
			},
			{
				fieldtype: 'Date',
				fieldname: "due_date",
				read_only: 1,
				in_list_view: 1,
				columns: 1,
				label: __('Due Date'),

			},
			{
				fieldtype: 'Currency',
				fieldname: "invoice_amount",
				
				read_only: 1,
				in_list_view: 1,
				columns: 1,
				label: __('Invoice Amount'),

			},
			{
				fieldtype: 'Currency',
				fieldname: "paid_amount",
				
				read_only: 1,
			
				label: __('Paid Amount'),
			},
			{
				fieldtype: 'Currency',
				fieldname: "credit_note",
				
				read_only: 1,
				
				label: __('Credit Note'),
			},
			{
				fieldtype: 'Currency',
				fieldname: "outstanding_amount",
				
				read_only: 1,
				in_list_view: 1,
				columns: 1,
				label: __('Total Outstanding'),
			}, 
			{
				fieldtype: 'Currency',
				fieldname: "total_due",
				
				read_only: 1,
				in_list_view: 1,
				columns: 1,
				label: __('Total Due'),
			},
			{
				fieldtype: 'Currency',
				fieldname: "commited_amount",
				
				default : 0,
				in_list_view: 1,
				columns: 1,
				label: __('Commited Amount'),
			},
			{
				fieldtype: 'Date',
				fieldname: "commited_date",
				
				in_list_view: 1,
				columns: 1,
				label: __('Commited Date'),

			},
			{
				fieldtype: 'Column Break'
			},
			{
				fieldtype: 'Currency',
				fieldname: "range1",
				
				read_only: 1,
				in_list_view: 1,
				columns: 1,
				label: ('0-30')
			},
			{
				fieldtype: 'Currency',
				fieldname: "range2",
				
				read_only: 1,
				
				label: ('31-60'),
			},
			{
				fieldtype: 'Currency',
				fieldname: "range3",
				
				read_only: 1,
			
				columns: 1,
				label: ('61-90'),
			},
			{
				fieldtype: 'Currency',
				fieldname: "range4",
				columns: 1,
				read_only: 1,
				
				label: ('91-120'),
			},
			{
				fieldtype: 'Currency',
				fieldname: "range5",
				read_only: 1,
			
				columns: 1,
				label: __('120-Above'),
			},
			{
				fieldtype: 'Int',
				fieldname: "age",
				read_only: 1,
				in_list_view: 1,
				columns: 1,
				label: __('Age'),
			},
			{
				fieldtype: 'Link',
				fieldname: "follow_up",
				read_only: 1,
				in_list_view: 1,
				columns: 1,
				label: __('Follow Up'),
				options: "Follow Up Level"
			},
			{
				fieldtype: 'Link',
				fieldname: "customer_group",
				read_only: 1,
				
				options: "Customer Group",
				columns: 1,
				label: __('Customer Group')
			},
			{
				fieldtype: 'Link',
				fieldname: "territory",
				read_only: 1,
				
				options: "Territory",
				columns: 1,
				label: __('Territory')
			},
		
		];

		var child_table = [
				{
					fieldtype: 'Link',
					fieldname: "customer",
					options: "Customer",
					default: child.customer,
					in_list_view: 1,
					columns: 1,
					label: __('Customer'),
				},
				{
					fieldtype: 'Data',
					fieldname: "customer_name",
					default: child.customer_name,
					read_only: 1,
					in_list_view: 1,
					columns: 1,
					label: __('Customer Name'),
				},
				{
					fieldtype: 'Column Break'
				},
				{
					fieldtype: 'Currency',
					fieldname: "range1",
					read_only: 1,
					in_list_view: 1,
					columns: 1,
					default: child.range1,
					label: ('0-30') 
				},
				{
					fieldtype: 'Currency',
					fieldname: "range2",
					default: child.range2,
					read_only: 1,
					in_list_view: 1,
					columns: 1,
					label: ('31-60')
				},
				{
					fieldtype: 'Currency',
					fieldname: "range3",
					default: child.range3,
					read_only: 1,
					in_list_view: 1,
					columns: 1,
					label: ('61-90'),
				},
				{
					fieldtype: 'Currency',
					fieldname: "range4",
					default: child.range4,
					read_only: 1,
					in_list_view: 1,
					label: ('91-120'),
				},
				{
					fieldtype: 'Currency',
					fieldname: "range5",
					default: child.range5,
					read_only: 1,
					in_list_view: 1,
					columns: 1,
					label: __('120-Above'),
				},
				{
					fieldtype: 'Section Break'
				},
				{
					fieldname: "trans_items",
					fieldtype: "Table",
					label: "Items",
					cannot_add_rows: 1,
					cannot_delete_rows : 1,
					in_place_edit: false,
					reqd: 1,
					read_only: 1,
					data: this.data,
					get_data: () => {
					 	return this.data;
					 },
					fields: fields
				},
				{
					fieldtype: 'Section Break'
				},
				{fieldtype: "Button",
				 label: __("Submit Commitment"), 
				 fieldname : "commitment"
				},
				{
					fieldtype: "Column Break"
				},
				{fieldtype: "Button",
				 label: __("Done"), 
				 fieldname : "done"
				},
				{
					fieldtype: "Column Break"
				},
				{
					fieldtype: 'Section Break'
				},
			]

		if (unique){
			
			unique.forEach(d => { 
				child_table.push({
					fieldtype : "Button",
					label: __(d),
					fieldname : d
				},
				{
					fieldtype: 'Column Break'
				})
			});

			
		}	
		console.log(" Line 164")
		const dialog = new frappe.ui.Dialog({
			title: __("Update Items"),
			fields: child_table,

			
			// Action button below dialog child table
			
			// primary_action: function () {
			// 	const trans_items = this.get_values()["trans_items"].filter((item) => !!item.item_code);
			// 	frappe.call({
			// 		method: 'erpnext.controllers.accounts_controller.update_child_qty_rate',
			// 		freeze: true,
			// 		args: {
			// 			'parent_doctype': frm.doc.doctype,
			// 			'trans_items': trans_items,
			// 			'parent_doctype_name': frm.doc.name,
			// 			'child_docname': child_docname
			// 		},
			// 		callback: function() {
			// 			frm.reload_doc();
			// 		}
			// 	});
			// 	this.hide();
			// 	refresh_field("items");
			// },
			// primary_action_label: __('Update')
		});
		// var q = frappe.model.get_value('Follow Up Level', {"no_of_days": ['<=',158]}, '')
		// frappe.model.get_value('Follow Up Level', {"no_of_days": ['<=',200]}, 'name',
  		// function(d) {
		// 	console.log("this is inside", d)
		//   })
		console.log(" Line 220")
		
		r.message.forEach(d => {
					dialog.fields_dict.trans_items.df.data.push({
				"voucher_type": d.voucher_type,
				"voucher_no": d.voucher_no,
				"due_date": d.due_date,
				"invoice_amount": d.invoice_grand_total,
				"paid_amount": d.paid,
				"credit_note": d.credit_note,
				"outstanding_amount": d.outstanding,
				"range1": d.range1,
				"range2": d.range2,
				"range3": d.range3,
				"range4": d.range4,
				"range5": d.range5,
				"__checked" : 1,
				"age" : d.age,
				"follow_up" : d.follow_up,	
				"territory" : d.territory,
				"customer_group" : d.customer_group,
				"total_due" : d.total_due
				
			});
			console.log(" Line 237")
			//dialog.fields_dict.trans_items.df.data = r.message;
			this.data = dialog.fields_dict.trans_items.df.data;
			dialog.fields_dict.trans_items.grid.refresh();
		})
		// $("[data-fieldname=update1]").on('click',function(){
		// 	var batch_name = $("input[data-fieldname='student_name']").val();
		// 	selectStudentIdFromStudentDocType(batch_name);
		// })

		dialog.fields_dict.commitment.input.onclick = function() {
			var batch_name = dialog.fields_dict.trans_items.df.get_data()
			frappe.call({
				method: 'on_submit_commitment',
				doc: frm.doc,
				freeze: true,
				args: {
					'trans_items' : trans_items,
					'customer' : child.customer
				}
			})
				// const trans_items = this.get_values()["trans_items"].filter((item) => !!item.item_code);
			// selectStudentIdFromStudentDocType(batch_name);
			console.log(" this is from inside of dialog customer", batch_name)
		}

		unique.forEach(d => {
			var trans_items = dialog.fields_dict.trans_items.df.get_data()
			let btn = dialog.fields_dict[d].input.onclick = function() {
				console.log(" nutoom", d)
				frappe.call({
							method: 'on_follow_up_button_click',
							doc : frm.doc,
							freeze: true,
							args: {
								'follow_up': d,
								'trans_items': trans_items,
								't_date': frm.doc.report_date,
								'customer': child.customer,
							},
							callback: function(r) {
								// frm.reload_doc();
								if (r.message){
									console.log(" this is call from follow Ups", r.message)
								}
							}
						});
			}
			//dinamic_btn
		})
		dialog.show();
		dialog.$wrapper.find('.modal-dialog').css("max-width", "80%");
		dialog.$wrapper.find('.modal-dialog').css("width", "80%");
	}
}

})
	}
})