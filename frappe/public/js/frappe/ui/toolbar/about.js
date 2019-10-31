frappe.provide('frappe.ui.misc');


function getGitChangelog(app){
    frappe.call({
        method:"frappe.utils.change_log.get_git_changelog",
        args: {
            app: app
        },
        callback: function(r) {
            console.log(r);
            r.message.map(rev => {
                let title = "<i style='font-size: 11px;'>" + rev[0] + "</i>";
                let msg = title + "<p style=\"margin-top: 0\">" + rev[1] + "</p>";
                frappe.msgprint(msg);
            });

        }
    });
}

frappe.ui.misc.about = function() {
	if(!frappe.ui.misc.about_dialog) {
		var d = new frappe.ui.Dialog({title: __('Frappe Framework')});

		$(d.body).html(repl("<div>\
		<p>"+__("Open Source Applications for the Web")+"</p>  \
		<p><i class='fa fa-globe fa-fw'></i>\
			Website: <a href='https://frappe.io' target='_blank'>https://frappe.io</a></p>\
		<p><i class='fa fa-github fa-fw'></i>\
			Source: <a href='https://github.com/frappe' target='_blank'>https://github.com/frappe</a></p>\
		<hr>\
		<h4>Installed Apps</h4>\
		<div id='about-app-versions'>Loading versions...</div>\
		<hr>\
		<p class='text-muted'>&copy; Frappe Technologies Pvt. Ltd and contributors </p> \
		</div>", frappe.app));

		frappe.ui.misc.about_dialog = d;

		frappe.ui.misc.about_dialog.on_page_show = function() {
			if(!frappe.versions) {
				frappe.call({
					method: "frappe.utils.change_log.get_versions",
					callback: function(r) {
						show_versions(r.message);
					}
				})
			} else {
				show_versions(frappe.versions);
			}
		};

		var show_versions = function(versions) {
			var $wrap = $("#about-app-versions").empty();
			$.each(Object.keys(versions).sort(), function(i, key) {
				var v = versions[key];
          v.title = '<a href="#"><b>' + v.title + ': </b></a>';
				if(v.branch) {
					  let title = $(v.title).click(() => getGitChangelog(key));
					  let text = $("<p>").append(title).append($.format('v{0} ({1})<br>',
                                                              [v.branch_version || v.version, v.branch]));
				    $(text).appendTo($wrap);
				} else {
					  let title = $(v.title).click(() => getGitChangelog(key));
					  let text = $("<p>").append(title).append($.format('v{0} <br>',
                                                              [v.branch_version || v.version]));
				    $(text).appendTo($wrap);
				}
			});

			frappe.versions = versions;
		}

	}

	frappe.ui.misc.about_dialog.show();

}
