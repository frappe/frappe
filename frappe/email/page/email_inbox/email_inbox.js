frappe.provide("frappe.email")

frappe.pages['email_inbox'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Email Inbox',
		icon: 'fa fa-inbox',
		single_column: false
	});

	frappe.model.with_doctype('Communication', function() {
		wrapper.inbox = new frappe.email.EmailInbox({
			method: 'frappe.desk.reportview.get',
			wrapper: wrapper,
			page: wrapper.page,
			no_loading: true
		});
	});
};

frappe.pages['email_inbox'].refresh = function(wrapper) {
	if (wrapper.inbox) {
		wrapper.inbox.refresh()
	}
};

frappe.email.EmailInbox = frappe.ui.Listing.extend({
    init: function(opts) {
		$.extend(this, opts);
		wrap = this;
		this.wrapper = opts.wrapper;
		this.page_length  = 20;
		this.start = 0;
		this.no_result_message = 'No Emails to Display';

		this.get_accounts();
    },

	setup_inbox: function() {
		var me = this;
		// setup listing
		me.make({
			doctype: 'Communication',
			page: me.page,
			method: 'frappe.desk.reportview.get',
			get_args: me.get_args,
			parent: me.page.main,
			start: 0,
			show_filters: true
		});

		this.render_sidebar();
		this.render_headers();
		this.render_buttons();
		this.init_select_all();
		this.setup_notifications();
		
		this.refresh();
   	},

    get_accounts: function() {
    	// get all the configured email account for the user

    	var me = this;
        frappe.call({
			method: 'frappe.email.page.email_inbox.get_accounts',
			args: {
				'user': user
			},
			callback:function(r){
				me.page.sidebar.empty()
				if(!r.message) {
					frappe.msgprint(__("No Email Account assigned to you. Please contact your System Administrator"));

					setTimeout(function() {
						if (frappe.session.user==="Administrator")
							frappe.set_route("List", "User");
						else 
							frappe.set_route('');
					}, 3000);
				}

				me.accounts = r.message;
				me.setup_inbox();
			}
		});
    },

	refresh:function(){
    	delete frappe.route_flags.create_contact;
		delete frappe.route_flags.update_contact;
		this.run();
	},

	render_sidebar: function (data) {
		var me = this;
        frappe.call({
			method: 'frappe.email.page.email_inbox.get_accounts',
			args:{user:frappe.user["name"]},
			async:false,
			callback:function(list){
				var buttons = '<div class="layout-main-section overlay-sidebar">';
				if (list["message"]){
					me.accounts = [];
					var rows = "";

					for (var i = 0;i<list["message"].length;i++)
					{
						rows += '<div class="list-row inbox-select"> <div class="row"><a class="inbox-item ellipsis col-md-12" title ="'+list["message"][i]["email_id"]+'" data-account="'+list["message"][i]["email_account"]+'" style="margin-left: 10px;">'+list["message"][i]["email_id"]+'</a> </div></div>';
						me.accounts.push({name:list["message"][i]["email_account"],email:list["message"][i]["email_id"]})
					}
					me.allaccounts = $.map(me.accounts,function(v){return v.name}).join(",");
					buttons += '<div class="list-row inbox-select list-row-head" style="font-weight:bold"> <div class="row"><a class="inbox-item ellipsis col-md-12 " title ="All Accounts" data-account="'+me.allaccounts+'" style="margin-left: 10px;">All Accounts</a> </div></div>';
					buttons += rows;
					buttons += '<div class="list-row inbox-select"> <div class="row"><a class="inbox-item ellipsis col-md-12 " title ="Sent" data-account="Sent" style="margin-left: 10px;">Sent</a> </div></div>';
					me.account = me.allaccounts;
					me.default_filters=[
						["Communication", "communication_type", "=", "Communication"],
						["Communication", "email_account", "in", me.account],
						["Communication", "sent_or_received", "=", "Received"]]

					me.page.sidebar.empty().append(buttons);
					$(".inbox-select").on("click",function(btn){
						me.account = $(btn.currentTarget).find(".inbox-item").data("account");
						$(me.page.sidebar).find(".list-row").removeClass("list-row-head").css("font-weight","normal");
						$(btn.currentTarget).closest(".list-row").addClass("list-row-head").css("font-weight","bold");
						me.cur_page = 1;
						$(me.page.main).find(".list-select-all,.list-row-checkbox").prop("checked",false);
						me.toggle_actions();

						if(me.account=="Sent"){
							me.filter_list.default_filters=[
								["Communication", "communication_type", "=", "Communication"],
								["Communication", "sent_or_received", "=", "Sent"]]
						}else {
							me.filter_list.default_filters = [
								["Communication", "communication_type", "=", "Communication"],
								["Communication", "email_account", "in", me.account],
								["Communication", "sent_or_received", "=", "Received"]];
						}
						me.filter_list.clear_filters();

						if (me.filter_list.reload_stats){me.filter_list.reload_stats()}
						me.refresh();
					});
				}
			}
        })
    },

   	toggle_accounts: function() {
		$(this.page.main).find(".list-select-all,.list-delete").prop("checked", false);
   		this.toggle_actions();

   		this.filter_list.clear_filters();
   		this.refresh();
   	},

   	render_headers: function(){
		$(".layout-main-section-wrapper").css("padding-left","0px").css("padding-right","0px");
		var data = {
			"start":this.start,
			"page_length":this.page_length.toString()
		};

		headers_html = frappe.render_template("inbox_headers", data)
		this.list_header = $(headers_html).appendTo(this.page.main.find(".list-headers"));
	},

	get_args: function(){
		var args = {
			doctype: this.doctype,
			fields: [
				"name", "sender", "sender_full_name", "communication_date", "recipients",
				"cc","communication_medium", "subject", "status" ,"reference_doctype", 
				"reference_name", "timeline_doctype", "timeline_name", "timeline_label",
				"sent_or_received", "uid", "message_id", "seen"
			],
			filters: this.get_email_filters(),
			order_by: 'communication_date desc',
			save_list_settings: false
		};

		return args;
	},

	get_email_filters: function() {
		filters = this.filter_list.get_filters()

		if(this.account == "Sent") {
			this.filter_list.default_filters = [
				["Communication", "communication_type", "=", "Communication"],
				["Communication", "communication_medium", "=", "Email"],
				["Communication", "user", "=", user],
				["Communication", "sent_or_received", "=", "Sent"]
			]
		} else {
			this.filter_list.default_filters = [
				["Communication", "communication_type", "=", "Communication"],
				["Communication", "communication_medium", "=", "Email"],
				["Communication", "sent_or_received", "=", "Received"],
				["Communication", "email_account", "in", this.account],
			]
		}

		$.extend(filters, this.filter_list.default_filters)
		return filters;
	},

	setup_notifications: function() {
		// setup real time email notification using frappe.realtime

		var me = this;
		frappe.realtime.on("new_email", function(data) {
			for(var i =0; i<me.accounts.length; i++) {
				if (data.account == me.accounts[i].name) {
					frappe.utils.notify(data.account, "you have "+data.number+" new emails", {}, function () {
						window.focus();
						me.account = data.account;
						$(me.page.sidebar).find(".list-row").removeClass("list-row-head").css("font-weight", "normal");
						$('.inbox-item[data-account="' + data.account + '" ]').closest(".list-row").addClass("list-row-head").css("font-weight","bold");
						me.refresh();
					});
					if(!me.fresh &&(data.account == me.account || me.account == me.all_accounts)) {
						me.fresh = true;
						me.refresh();
					}
				}
			}
			me.fresh = false
		});
	},

	render_list: function(data) {
		var me = this
		$(me.wrapper).find(".result-list").empty();

		$.each(data, function(idx, email) {
			$(frappe.render_template("inbox_list", {data: email}))
				.data("data", email)
				.appendTo($(me.wrapper).find(".result-list"))
		});

		//click action
		$(me.wrapper).find(".result-list").find(".list-row").click(function(btn) {
			if ($(btn.target).hasClass("noclick"))
				return
			
			var row = $(btn.target).closest(".list-row").data("data");
			if($(btn.target).hasClass("relink-link")){
				me.relink(row);
				return
			}

			if(me.account != "Sent") {
				if ($(btn.target).hasClass("company-link")) {
					me.company_select(row, true);
					return
				}
			}
			me.email_open(row);
		});
	},

	company_select: function(row, nomatch) {
		var me = this;
		var fields = [
			{
				"fieldtype": "Heading",
				"label": __("Create new Contact to Match Email Address"),
				"fieldname": "Option1"
			},
			{
				"fieldtype": "Button",
				"label": __("Create/Add new Contact"),
				"fieldname":"newcontact",
				"description": __('Create new Contact for a Customer, Supplier, User or Organisation to Match "') + row.sender + __('" Against')
			}
		];

		if (!nomatch) {
			fields.push({
				"fieldtype": "Heading",
				"label": __("Do not Match"),
				"fieldname": "Option3"
				});
			fields.push({
					"fieldtype": "Button",
					"label": __("Do not Match"),
					"fieldname":"nomatch"
				})
		}

		var d = new frappe.ui.Dialog ({
			title: __("Match Emails to a Company"),
			fields: fields
		});

		d.get_input("newcontact").on("click", function (frm) {
			d.hide();
			delete frappe.route_flags.update_contact;
			frappe.route_flags.create_contact = 1;
			var name_split = row.sender_full_name?row.sender_full_name.split(' '):["",""];
			row.nomatch = 1;

			frappe.route_options = {
				"email_id": row.sender,
				"first_name": name_split[0],
				"last_name":name_split[name_split.length-1],
				"status": "Passive"
			};
			frappe.model.with_doctype("Contact", function() {
				var doc = frappe.model.get_new_doc("Contact");
				frappe.set_route("Form", "Contact", doc.name);
			})
		});

		if (!nomatch) {
			d.get_input("nomatch").on("click", function (frm) {
				d.hide();
				frappe.call({
					method: 'frappe.email.page.email_inbox.setnomatch',
					args: {
						name: row.name
					}
				});
				row.nomatch = 1;
				if (!nomatch) {
					me.email_open(row)
				}
			});
		}
		d.show();
	},

	email_open: function(row) {
		var me = this;
		me.actions_opened = false;
		if(me.open_email == row.name){
			return
		}
		me.open_email = row.name

		//mark email as read
		if(me.account!="Sent") {
			this.mark_read(row);
		}
		//start of open email

		var emailitem = new frappe.ui.Dialog ({
                title: __(row.subject),
                fields: [{
                    "fieldtype": "HTML",
                    "fieldname": "email"
                }]
            });
		//prompt for match
		if (!row.timeline_label && !row.nomatch && me.account!="Sent") {
			setTimeout(function () {
				if (frappe.ui.open_dialogs.indexOf(emailitem) != -1 && !me.actions_opened) {
					me.company_select(row)
				}}, 4000);
		}

		var c = me.prepare_email(row);
		emailitem.fields_dict.email.$wrapper.html(frappe.render_template("inbox_email", {data:c}));
      $(emailitem.$wrapper).find(".reply").find("a").attr("target", "_blank");

		//Action buttons
		$(emailitem.$wrapper).find(".text-right").prepend(frappe.render_template("inbox_email_actions",{data:row})).on("click", function () {
			me.actions_opened = true;
		});
		$(emailitem.$wrapper).find(".relink-link").on("click", function () {
			me.relink(row); });
		$(emailitem.$wrapper).find(".delete-link").on("click", function () {
			me.delete_email({n:row.name, u:row.uid});
			emailitem.hide()
		});

		$(emailitem.$wrapper).find(".company-link").on("click", function () {
			me.company_select(row, true)});
		me.add_reply_btn_event(emailitem, c);

		//adjust sizing
		$(".modal-dialog").addClass("modal-lg");
		$(emailitem.$wrapper).find(".modal-title")
			.parent()
			.removeClass("col-xs-7")
			.addClass("col-xs-7 col-sm-8 col-md-9");
		
		$(emailitem.$wrapper).find(".text-right")
			.parent()
			.removeClass("col-xs-5")
			.addClass("col-xs-5 col-sm-4 col-md-3");

		//setup close
		emailitem.onhide = function() {
			me.open_email = null
		}

		emailitem.show();
	},

	add_reply_btn_event: function (emailitem, c) {
        var me = this;
		
		//reply
        $(emailitem.$wrapper).find(".reply-link").on("click", function () {
            var sender = "";
			for (var i=0;i<me.accounts.length;i++){
				if(me.accounts[i].name===me.account){
					sender =  me.accounts[i].email;
					break;
				}
			}
			new frappe.views.CommunicationComposer({
				doc: {
					doctype: c.reference_doctype,
					name: c.reference_name
				},
				sender: sender,
				subject: "Re: " + c.subject,
				recipients: c.sender,
				last_email: c,
				attachments: c.attachments
			});
        });
		
		//reply-all
		$(emailitem.$wrapper).find(".reply-all-link").on("click", function () {
            var sender = "";
			for (var i=0;i<me.accounts.length;i++){
				if(me.accounts[i].name===me.account){
					sender =  me.accounts[i].email;
					break;
				}
			}
			new frappe.views.CommunicationComposer({
				doc: {
					doctype: c.reference_doctype,
					name: c.reference_name
				},
				sender:sender,
				subject: "Re: " + c.subject,
				recipients: (c.sender + (c.recipients ? ", "+c.recipients:"") + (c.cc ? ", "+c.cc:"")).replace(sender,""),
				last_email: c,
				attachments:c.attachments
			});
        });
		
		//forward
		$(emailitem.$wrapper).find(".forward-link").on("click", function () {
            var sender = "";
			for (var i=0;i<me.accounts.length;i++){
				if(me.accounts[i].name===me.account){
					sender =  me.accounts[i].email;
					break;
				}
			}
			var communication = new frappe.views.CommunicationComposer({
				doc: {
					doctype: c.reference_doctype,
					name: c.reference_name
				},
				sender:sender,
				subject: "FW: " + c.subject,
				last_email: c,
				forward:true,
				attachments:c.attachments
			});

			$(communication.dialog.fields_dict.select_attachments.wrapper).find("input[type=checkbox]").prop("checked",true)
        });
    },

	relink: function(row){
		var me = this;
		var callback = function(frm){
			$(me.wrapper).find(".row-named[data-name="+row.name+"]").find(".reference-document")
				.html(values["reference_name"])
			.attr("href",'#Form/'+values["reference_doctype"]+ '/'+values["reference_name"])
			.attr("title","Linked Doctype: "+values["reference_doctype"]);
			row.reference_doctype = values["reference_doctype"];
			row.reference_name = values["reference_name"];
		}
		frappe.timeline.relink_dialog(row.name, row.reference_doctype, row.reference_name, callback);
	},

	prepare_email: function(c){
		var me = this;
		frappe.call({
			method:'frappe.email.page.email_inbox.get_email_content',
			args:{
				doctype:"Communication",
				name:c.name
			},
			async:false,
			callback:function(r){
				c.attachments =r["message"][0];
				c.content = r["message"][1];
			}
		});
		c.doctype = "Communication";
        c.comment_on = comment_when(c.communication_date);


        if (c.attachments && typeof c.attachments === "string")
            c.attachments = JSON.parse(c.attachments);

        if (!c.comment_type)
            c.comment_type = "Email";

		c.comment = c.content;
        if (c.comment_type == "Email") {
            c.comment = c.comment.split("<!-- original-reply -->")[0];
            c.comment = frappe.utils.strip_original_content(c.comment);
            c.comment = frappe.dom.remove_script_and_style(c.comment);

            c.original_comment = c.comment;
            c.comment = frappe.utils.toggle_blockquote(c.comment);
        }


        if (!frappe.utils.is_html(c.comment)) {
            c.comment_html = frappe.markdown(__(c.comment));
        } else {
            c.comment_html = c.comment;
            c.comment_html = frappe.utils.strip_whitespace(c.comment_html);
			c.comment_html = c.comment_html.replace(/&lt;/g,"<").replace(/&gt;/g,">")
        }

        // bold @mentions
        if (c.comment_type === "Comment") {
            c.comment_html = c.comment_html.replace(/(^|\W)(@\w+)/g, "$1<b>$2</b>");
        }

		return c
	},

    init_select_all: function () {
        var me = this;

		$(".list-select-all").on("click", function () {
			$(me.wrapper).find('.list-row-checkbox').prop("checked", $(this).prop("checked"));
			me.toggle_actions();
		});

		$(me.wrapper).on("click", ".list-row-checkbox", function (event) {
			me.toggle_actions();

			// multi-select using shift key
			var $this = $(this);
			if (event.shiftKey && $this.prop("checked")) {
				var $end_row = $this.parents(".list-row");
				var $start_row = $end_row.prevAll(".list-row")
					.find(".list-row-checkbox:checked").last().parents(".list-row");
				if ($start_row) {
					$start_row.nextUntil($end_row).find(".list-row-checkbox").prop("checked", true);
				}
			}
		});

		// after delete, hide delete button
		me.toggle_actions();
    },

	render_buttons: function(){
		var me = this;

		me.page.add_action_item("Delete", function(){ me.delete_email() });
		me.page.add_action_item("Mark as Unread", function(){ me.mark_unread() });
		me.page.add_action_item("Mark as Read", function(){ me.mark_read() });

		me.page.set_primary_action("New Email", function(){
			var sender = "";
			for (var i=0;i<me.accounts.length;i++){
				if(me.accounts[i].name===me.account){
					sender =  me.accounts[i].email
					break;
				}
			}
			new frappe.views.CommunicationComposer({
					doc: {},
					sender: sender
			});
		}, "fa-plus", "New Email");
	},

    toggle_actions: function () {
        var me = this;
        if (me.page.main.find(".list-row-checkbox:checked").length) {
            //show buttons
			$(me.page.actions_btn_group).show();
			$(me.page.btn_primary).hide()
        } else {
            //hide button
			$(me.page.actions_btn_group).hide();
			$(me.page.btn_primary).show()
        }
    },

	delete_email: function(data){
		var me = this;
		if (!data) {
			var names = $.map(me.action_checked_items('.data("data")'), function(v){
				return {name:v.name, uid:v.uid}
			});
			me.action_checked_items('.remove()')
		} else {
			var names = [{name:data.name, uid:data.uid}]
		}
	},

	mark_unread: function(){
		var me = this;
		var names = $.map(me.action_checked_items('.data("data")'), function(v){
			return {name:v.name, uid:v.uid}
		});
		me.create_flag_queue(names, "Unread", "SEEN");
		me.action_checked_items('.css("font-weight", "BOLD")');
		me.update_local_flags(names, "seen", "0")
	},

	mark_read: function(data){
		var me = this;
		if (!data) {
			var names = $.map(me.action_checked_items('.data("data")'), function(v){return {name:v.name, uid:v.uid}});
			me.action_checked_items('.css("font-weight", "normal")')
		} else {
			var names = [{name:data.name, uid:data.uid}];
			$(".row-named").filter("[data-name=" + data.name + "]").css("font-weight", "normal")
		}
		me.create_flag_queue(names, "Read", "SEEN");
		me.update_local_flags(names, "seen", "1");
	},

	create_flag_queue: function(names, action, flag){
		frappe.call({
			method: 'frappe.email.page.email_inbox.create_flag_queue',
			args:{
				names: JSON.stringify(names),
				action: action,
				flag: flag
			}
		})
	},

	update_local_flags:function(names,field,val){
		frappe.call({
			method: 'frappe.email.page.email_inbox.update_local_flags',
			args:{
				names: JSON.stringify(names),
				field: field,
				val: val
			}
		})
		$('.list-row-checkbox:checked').prop( "checked", false );
	},

	action_checked_items: function(action) {
		return $.map(this.page.main.find('.list-row-checkbox:checked'), function(e) {
			return eval('$(e).closest(".row-named")'+action);
		});
	},
});