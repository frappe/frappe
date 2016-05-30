// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

frappe.provide('frappe.timeline');

frappe.ui.form.Timeline = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
		this.make();
	},
	make: function() {
		var me = this;
		this.wrapper = $(frappe.render_template("timeline",
			{})).appendTo(this.parent);

		this.list = this.wrapper.find(".timeline-items");
		this.input = this.wrapper.find(".form-control");

		this.comment_button = this.wrapper.find(".btn-comment")
			.on("click", function() {
				me.add_comment(this);
			});

		this.input.keydown("meta+return ctrl+return", function(e) {
			me.comment_button.trigger("click");
		});

		this.email_button = this.wrapper.find(".btn-new-email")
			.on("click", function() {
				new frappe.views.CommunicationComposer({
					doc: me.frm.doc,
					txt: frappe.markdown(me.input.val()),
					frm: me.frm,
					recipients: me.get_recipient()
				})
			});

		this.list.on("click", ".toggle-blockquote", function() {
			$(this).parent().siblings("blockquote").toggleClass("hidden");
		});

		this.setup_comment_like();

		this.setup_mentions();

		this.list.on("click", ".btn-more", function() {
			var communications = me.get_communications();
			frappe.call({
				btn: this,
				method: "frappe.desk.form.load.get_communications",
				args: {
					doctype: me.frm.doc.doctype,
					name: me.frm.doc.name,
					start: communications.length
				},
				callback: function(r) {
					if (!r.exc) {
						if (r.message) {
							var new_communications = r.message;
							var communications = me.get_communications().concat(new_communications);
							frappe.model.set_docinfo(me.frm.doc.doctype, me.frm.doc.name, "communications", communications);

						} else {
							me.more = false;
						}

						me.refresh();
					}
				}
			});
		});

	},

	refresh: function(scroll_to_end) {
		var me = this;

		this.last_type = "Comment";

		if(this.frm.doc.__islocal) {
			this.wrapper.toggle(false);
			return;
		}
		this.wrapper.toggle(true);
		this.list.empty();

		// var communications = [].concat(this.get_communications());

		var communications = this.get_communications();

		$.each(communications.sort(function(a, b) { return a.creation > b.creation ? -1 : 1 }),
			function(i, c) {
				if(c.content) {
					c.frm = me.frm;
					me.render_timeline_item(c);
				}
		});

		// more btn
		if (this.more===undefined && communications.length===20) {
			this.more = true;
		}

		if (this.more) {
			var $more = $('<div class="timeline-item">\
				<button class="btn btn-default btn-xs btn-more">More</button>\
			</div>').appendTo(me.list);
		}

		// created
		me.render_timeline_item({"content": __("Created"), "comment_type": "Created", "communication_type": "Comment",
			"sender": this.frm.doc.owner, "creation": this.frm.doc.creation, "frm": this.frm});

		this.wrapper.find(".is-email").prop("checked", this.last_type==="Email").change();

		this.frm.sidebar.refresh_comments();

	},

	render_timeline_item: function(c) {
		var me = this;
		this.prepare_timeline_item(c);

		var $timeline_item = $(frappe.render_template("timeline_item", {data:c}))
			.appendTo(me.list)
			.on("click", ".close", function() {
				var name = $(this).parents(".timeline-item:first").attr("data-name");
				me.delete_comment(name);
				return false;
			});


		if(c.communication_type=="Communication" && c.communication_medium==="Email") {
			this.last_type = c.communication_medium;
			this.add_reply_btn_event($timeline_item, c);
			this.add_relink_btn_event($timeline_item, c);
		}

	},

	add_reply_btn_event: function($timeline_item, c) {
		var me = this;
		$timeline_item.find(".reply-link").on("click", function() {
			var name = $(this).attr("data-name");
			var last_email = null;

			// find the email tor reply to
			me.get_communications().forEach(function(c) {
				if(c.name==name) {
					last_email = c;
					return false;
				}
			});

			// make the composer
			new frappe.views.CommunicationComposer({
				doc: me.frm.doc,
				txt: "",
				frm: me.frm,
				last_email: last_email
			});
		});
	},

	add_relink_btn_event: function($timeline_item, c) {
		var me = this;
		$timeline_item.find(".relink-link").on("click", function() {
			var name = $(this).attr("data-name");
			var lib ="frappe.desk.doctype.communication_reconciliation.communication_reconciliation"
			var d = new frappe.ui.Dialog({
				title: __("Relink Communication"),
				fields: [{
                            "fieldtype": "Link",
                            "options": "DocType",
                            "label": __("Reference Doctype"),
					"name":"reference_doctype",
					"reqd": 1,
					"get_query": function() {
					return {
						query: lib+".get_communication_doctype"
						}
					}
                        },
                        {
	                	"fieldtype": "Dynamic Link",
	                	"options": "reference_doctype",
	                	"label": __("Reference Name"),
	                	"reqd": 1,
				"name":"reference_name"
                        }]
			});
			d.set_value("reference_doctype",cur_frm.doctype)
			d.set_value("reference_name",cur_frm.docname)
			d.set_primary_action(__("Relink"), function() {
				values = d.get_values()
                		if (values) {
					frappe.confirm(
    					'Are you sure you want to relink this communication to '+d.get_value("reference_name")+'?',
    					function(){
					frappe.call({
						method: lib+".relink",
						args: {
							"name": name,
							"reference_doctype": d.get_value("reference_doctype"),
							"reference_name": d.get_value("reference_name")
						},

						callback: function (frm) {
							$timeline_item.hide()
							d.hide();
							return false;
						}})
							},
							function(){
								show_alert('Document not Relinked')
						})
                		}
			});
			d.show();
		});

	},

	prepare_timeline_item: function(c) {
		if(c.communication_type=="Comment" && (c.comment_type || "Comment") === "Comment" && frappe.model.can_delete("Communication")) {
			c["delete"] = '<a class="close" href="#"><i class="octicon octicon-trashcan"></i></a>';
		} else {
			c["delete"] = "";
		}

		if(!c.sender) c.sender = this.frm.doc.owner;

		if(c.sender && c.sender.indexOf("<")!==-1) {
			c.sender = c.sender.split("<")[1].split(">")[0];
		}

		if(c.sender) {
			c.user_info = frappe.user_info(c.sender);
		} else {
			c.user_info = frappe.user_info(c.owner);
		}

		c.comment_on = comment_when(c.creation);
		c.fullname = c.sender_full_name || frappe.user.full_name(c.sender);

		if(c.attachments && typeof c.attachments==="string")
			c.attachments = JSON.parse(c.attachments);

		if(c.communication_type=="Comment" && !c.comment_type) {
			c.comment_type = "Comment";
		}

		this.set_icon_and_color(c);

		// label view
		if(c.comment_type==="Workflow" || c.comment_type==="Label") {
			c.comment_html = repl('<span class="label label-%(style)s">%(text)s</span>', {
				style: frappe.utils.guess_style(c.content),
				text: __(c.content)
			});
		} else {
			if(c.communication_type=="Communication" && c.communication_medium=="Email") {
				c.content = c.content.split("<!-- original-reply -->")[0];
				c.content = frappe.utils.strip_original_content(c.content);

				c.original_content = c.content;
				c.content = frappe.utils.toggle_blockquote(c.content);
			}

			if(!frappe.utils.is_html(c.content)) {
				c.content_html = frappe.markdown(__(c.content));
			} else {
				c.content_html = c.content;
				c.content_html = frappe.utils.strip_whitespace(c.content_html);
				c.comment_html = c.content_html.replace(/&lt;/g,"<").replace(/&gt;/g,">")
			}

			// bold @mentions
			if(c.comment_type==="Comment") {
				c.content_html = c.content_html.replace(/(^|\W)(@\w+)/g, "$1<b>$2</b>");
			}

			if (this.is_communication_or_comment(c)) {
				c.user_content = true;
				if (!$.isArray(c._liked_by)) {
					c._liked_by = JSON.parse(c._liked_by || "[]");
				}

				c.liked_by_user = c._liked_by.indexOf(user)!==-1;
			}
		}

		// basic level of XSS protection
		c.content_html = frappe.dom.remove_script_and_style(c.content_html);
	},

	is_communication_or_comment: function(c) {
		return c.communication_type==="Communication" || (c.communication_type==="Comment" && (c.comment_type==="Comment"||c.comment_type==="Relinked"));
	},

	set_icon_and_color: function(c) {
		c.icon = {
			"Email": "octicon octicon-mail",
			"Chat": "octicon octicon-comment-discussion",
			"Phone": "octicon octicon-device-mobile",
			"SMS": "octicon octicon-comment",
			"Created": "octicon octicon-plus",
			"Submitted": "octicon octicon-lock",
			"Cancelled": "octicon octicon-x",
			"Assigned": "octicon octicon-person",
			"Assignment Completed": "octicon octicon-check",
			"Comment": "octicon octicon-comment-discussion",
			"Workflow": "octicon octicon-git-branch",
			"Label": "octicon octicon-tag",
			"Attachment": "octicon octicon-cloud-upload",
			"Attachment Removed": "octicon octicon-trashcan",
			"Shared": "octicon octicon-eye",
			"Unshared": "octicon octicon-circle-slash",
			"Like": "octicon octicon-heart",
			"Relinked": "octicon octicon-check"
		}[c.comment_type || c.communication_medium]

		c.color = {
			"Email": "#3498db",
			"Chat": "#3498db",
			"Phone": "#3498db",
			"SMS": "#3498db",
			"Created": "#1abc9c",
			"Submitted": "#1abc9c",
			"Cancelled": "#c0392b",
			"Assigned": "#f39c12",
			"Assignment Completed": "#16a085",
			"Comment": "#f39c12",
			"Workflow": "#2c3e50",
			"Label": "#2c3e50",
			"Attachment": "#7f8c8d",
			"Attachment Removed": "#eee",
			"Relinked": "#16a085"
		}[c.comment_type || c.communication_medium];

		c.icon_fg = {
			"Attachment Removed": "#333",
		}[c.comment_type || c.communication_medium]

		if(!c.icon_fg)
			c.icon_fg = "#fff";

	},
	get_communications: function() {
		return this.frm.get_docinfo().communications;
	},
	add_comment: function(btn) {
		var txt = this.input.val();

		if(txt) {
			this.insert_comment("Comment", txt, btn, this.input);
		}
	},
	insert_comment: function(comment_type, comment, btn, input) {
		var me = this;
		if(input) input.prop('disabled', true);
		return frappe.call({
			method: "frappe.desk.form.utils.add_comment",
			args: {
				doc:{
					doctype: "Communication",
					communication_type: "Comment",
					comment_type: comment_type || "Comment",
					reference_doctype: this.frm.doctype,
					reference_name: this.frm.docname,
					content: comment,
					sender: user
				}
			},
			btn: btn,
			callback: function(r) {
				if(!r.exc) {
					me.input.val("");

					frappe.utils.play_sound("click");

					var comment = r.message;
					var comments = me.get_communications();
					var comment_exists = false;
					for (var i=0, l=comments.length; i<l; i++) {
						if (comments[i].name==comment.name) {
							comment_exists = true;
							break;
						}
					}
					if (comment_exists) {
						return;
					}

					me.frm.get_docinfo().communications = comments.concat([r.message]);
					me.refresh(true);
				}
			},
			always: function() {
				if(input) input.prop('disabled', false);
			}
		});

	},

	delete_comment: function(name) {
		var me = this;
		return frappe.call({
			method: "frappe.client.delete",
			args: {
				doctype: "Communication",
				name: name
			},
			callback: function(r) {
				if(!r.exc) {
					frappe.utils.play_sound("delete");

					me.frm.get_docinfo().communications =
						$.map(me.frm.get_docinfo().communications,
							function(v) {
								if(v.name==name) return null;
								else return v;
							}
						);
					me.refresh(true);
				}
			}
		});
	},

	get_recipient: function() {
		if(this.frm.email_field) {
			return this.frm.doc[this.frm.email_field];
		} else {
			return this.frm.doc.email_id || this.frm.doc.email || "";
		}
	},

	get_last_email: function(from_recipient) {
		var last_email = null,
			communications = this.frm.get_docinfo().communications,
			email = this.get_recipient();

		$.each(communications.sort(function(a, b) { return a.creation > b.creation ? -1 : 1 }), function(i, c) {
			if(c.communication_type=='Communication' && c.communication_medium=="Email") {
				if(from_recipient) {
					if(c.sender.indexOf(email)!==-1) {
						last_email = c;
						return false;
					}
				} else {
					last_email = c;
					return false;
				}
			}
		});

		return last_email;
	},

	setup_mentions: function() {
		var me = this;

		this.cursor_from = this.cursor_to = 0
		this.codes = $.ui.keyCode;
		this.up = $.Event("keydown", {"keyCode": this.codes.UP});
		this.down = $.Event("keydown", {"keyCode": this.codes.DOWN});
		this.enter = $.Event("keydown", {"keyCode": this.codes.ENTER});

		this.setup_autocomplete_for_mentions();

		this.setup_textarea_event();
	},

	setup_autocomplete_for_mentions: function() {
		var me = this;

		var username_user_map = {};
		for (var name in frappe.boot.user_info) {
			if(name !== "Administrator" && name !== "Guest") {
				var _user = frappe.boot.user_info[name];
				username_user_map[_user.username] = _user;
			}
		}

		this.mention_input = this.wrapper.find(".mention-input");

		var source = Object.keys(username_user_map);
		source.sort();

		this.mention_input.autocomplete({
			minLength: 0,
			autoFocus: true,
			source: source,
			select: function(event, ui) {
				var value = ui.item.value;
				var textarea_value = me.input.val();

				var new_value = textarea_value.substring(0, me.cursor_from)
					+ value
					+ textarea_value.substring(me.cursor_to);

				me.input.val(new_value);

				var new_cursor_location = me.cursor_from + value.length;

				// move cursor to right position
				if (me.input[0].setSelectionRange) {
					me.input.focus();
					me.input[0].setSelectionRange(new_cursor_location, new_cursor_location);

				} else if (me.input[0].createTextRange) {
					var range = input[0].createTextRange();
					range.collapse(true);
					range.moveEnd('character', new_cursor_location);
					range.moveStart('character', new_cursor_location);
					range.select();

				} else {
					me.input.focus();
				}
			}
		});

		this.mention_widget = this.mention_input.autocomplete("widget");

		this.autocomplete_open = false;
		this.mention_input
			.on('autocompleteclose', function() {
				me.autocomplete_open = false;
			})
			.on('autocompleteopen', function() {
				me.autocomplete_open = true;
			});

		// dirty hack to prevent backspace from navigating back to history
		$(document).on("keydown", function(e) {
			if (e.which===me.codes.BACKSPACE && me.autocomplete_open && document.activeElement==me.mention_widget.get(0)) {
				// me.input.focus();

				return false;
			}
		});
	},

	setup_textarea_event: function() {
		var me = this;

		// binding this in keyup to get the value after it is set in textarea
		this.input.keyup(function(e) {
			if (e.which===16) {
				// don't trigger for shift
				return;

			} else if ([me.codes.UP, me.codes.DOWN].indexOf(e.which)!==-1) {
				// focus on autocomplete if up and down arrows
				if (me.autocomplete_open) {
					me.mention_widget.focus();
					me.mention_widget.trigger(e.which===me.codes.UP ? me.up : me.down);
				}
				return;

			} else if ([me.codes.ENTER, me.codes.ESCAPE, me.codes.TAB, me.codes.SPACE].indexOf(e.which)!==-1) {
				me.mention_input.autocomplete("close");
				return;

			} else if (e.which !== 0 && !e.ctrlKey && !e.metaKey && !e.altKey) {
				if(!String.fromCharCode(e.which)) {
					// no point in parsing it if it is not a character key
					return;
				}
			}

			var value = $(this).val() || "";
			var i = e.target.selectionStart;
			var key = value[i-1];
			var substring = value.substring(0, i);
			var mention = substring.match(/(?=[^\w]|^)@([\w]*)$/);

			if (mention && mention.length) {
				var mention = mention[0].slice(1);

				// record location of cursor
				me.cursor_from = i - mention.length;
				me.cursor_to = i;

				// render autocomplete at the bottom of the textbox and search for mention
				me.mention_input.autocomplete("option", "position", {
					of: me.input,
					my: "left top",
					at: "left bottom"
				});
				me.mention_input.autocomplete("search", mention);

			} else {
				me.cursor_from = me.cursor_to = 0;
				me.mention_input.autocomplete("close");
			}
		});

		// binding this in keydown to prevent default action
		this.input.keydown(function(e) {
			// enter, escape, tab
			if (me.autocomplete_open) {
				if ([me.codes.ENTER, me.codes.TAB].indexOf(e.which)!==-1) {
					// set focused value
					me.mention_widget.trigger(me.enter);

					// prevent default
					return false;
				}
			} else {
				if (e.which==me.codes.TAB) {
					me.comment_button.focus();

					return false;
				}
			}
		});
	},

	setup_comment_like: function() {
		this.wrapper.on("click", ".comment-likes .octicon-heart", frappe.ui.click_toggle_like);

		frappe.ui.setup_like_popover(this.wrapper, ".comment-likes");
	}
});

$.extend(frappe.timeline, {
	new_communication: function(communication) {
		var docinfo = frappe.model.get_docinfo(communication.reference_doctype, communication.reference_name);
		if (docinfo && docinfo.communications) {
			var communications = docinfo.communications;
			var communication_exists = false;
			for (var i=0, l=communications.length; i<l; i++) {
				if (communications[i].name==communication.name) {
					communication_exists = true;
					break;
				}
			}

			if (!communication_exists) {
				docinfo.communications = communications.concat([communication]);
			}
		}

		if (cur_frm.doctype === communication.reference_doctype && cur_frm.docname === communication.reference_name) {
			cur_frm.timeline && cur_frm.timeline.refresh();
		}
	},

	delete_communication: function(communication) {
		var docinfo = frappe.model.get_docinfo(communication.reference_doctype, communication.reference_name);
		var index = frappe.timeline.index_of_communication(communication, docinfo);
		if (index !== -1) {
			// remove it from communications list
			docinfo.communications.splice(index, 1);
		}

		if (cur_frm.doctype === communication.reference_doctype && cur_frm.docname === communication.reference_name) {
			cur_frm.timeline && cur_frm.timeline.refresh();
		}
	},

	update_communication: function(communication) {
		var docinfo = frappe.model.get_docinfo(communication.reference_doctype, communication.reference_name);
		var index = frappe.timeline.index_of_communication(communication, docinfo);

		if (index !== -1) {
			// update
			$.extend(docinfo.communications[index], communication);
		}

		if (cur_frm.doctype === communication.reference_doctype && cur_frm.docname === communication.reference_name) {
			cur_frm.timeline && cur_frm.timeline.refresh();
		}
	},

	index_of_communication: function(communication, docinfo) {
		var index = -1;

		if (docinfo && docinfo.communications) {
			var communications = docinfo.communications;

			for (var i=0, l=communications.length; i<l; i++) {
				if (communications[i].name==communication.name) {
					index = i;
					break;
				}
			}
		}

		return index;
	},
})
