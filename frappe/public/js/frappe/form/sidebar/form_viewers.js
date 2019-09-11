function openChatWith(viewer){
		function displayRoom(room){
				// frappe.chatter.render({room: room});
				/* The above may be the way to go to display the chat,
					 but it inserts a completely new chat into the dom
					 which will lead to issues with toggeling the chat
					 using the normal toggle function in the page header
				*/
				//Ugly, but I don't find a better way
				frappe.chat.widget.props.children[0].attributes.click(room);
		}

		frappe.chat.widget.toggle(true);				// display Chat
		frappe.chat.room.get().then(
				function (rooms) {
						if (! Array.isArray(rooms)){
								rooms = [rooms];
						}
						let directChatsWithViewer = rooms.filter(function(room) {
								return room.type === "Direct" &&
										(room.owner === viewer || room.users.includes(viewer));
						});
						if (directChatsWithViewer.length > 0){
								displayRoom(directChatsWithViewer[0]);
						} else {
								frappe.chat.room.create("Direct", null, viewer).then(room => displayRoom(room));
						}
				});
		return false;	 /*  Becuase we execute this method onClick, it is very important to disable the
											 onClick listeners to bubble up by returning false.
											 The document onClick would trigger and make the chat widget invisible again */
}



frappe.ui.form.Viewers = Class.extend({
	init: function(opts) {
		$.extend(this, opts);
	},
	get_viewers: function() {
		let docinfo = this.frm.get_docinfo();
		if (docinfo) {
			return docinfo.viewers || {};
		} else {
			return {};
		}
	},
	refresh: function(data_updated) {
		this.parent.empty();

		var viewers = this.get_viewers();

		var users = [];
		var new_users = [];
		for (var i=0, l=(viewers.current || []).length; i < l; i++) {
			var username = viewers.current[i];
			if (username===frappe.session.user) {
				// current user
				continue;
			}

			var user_info = frappe.user_info(username);
			users.push({
				image: user_info.image,
				fullname: user_info.fullname,
				abbr: user_info.abbr,
				username: username,
				color: user_info.color,
				title: __("{0} is currently viewing this document", [user_info.fullname])
			});

			if (viewers.new.indexOf(username)!==-1) {
				new_users.push(user_info.fullname);
			}
		}

		if (users.length) {
			this.parent.parent().removeClass("hidden");
			this.parent.append(frappe.render_template("users_in_sidebar", {"users": users}));
			this.parent.find(".avatar").on("click", function(e) {
					return openChatWith($(e.currentTarget).data('username'));
			});

		} else {
			this.parent.parent().addClass("hidden");
		}

		if (data_updated && new_users.length) {
			// new user viewing this document, who wasn't viewing in the past
			if (new_users.length===1) {
				frappe.show_alert(__("{0} is currently viewing this document", [new_users[0]]));
			} else {
				frappe.show_alert(__("{0} are currently viewing this document", [frappe.utils.comma_and(new_users)]));
			}

		}
	}
});

frappe.ui.form.set_viewers = function(data) {
	var doctype = data.doctype;
	var docname = data.docname;
	var docinfo = frappe.model.get_docinfo(doctype, docname);
	var past_viewers = ((docinfo && docinfo.viewers) || {}).past || [];
	var viewers = data.viewers || [];

	var new_viewers = viewers.filter(viewer => !past_viewers.includes(viewer));

	frappe.model.set_docinfo(doctype, docname, "viewers", {
		past: past_viewers.concat(new_viewers),
		new: new_viewers,
		current: viewers
	});

	if (cur_frm && cur_frm.doc && cur_frm.doc.doctype===doctype && cur_frm.doc.name==docname) {
		cur_frm.viewers.refresh(true);
	}
}
