nts.provide("nts.ui.misc");
nts.ui.misc.about = function () {
	if (!nts.ui.misc.about_dialog) {
		var d = new nts.ui.Dialog({ title: __("nts Framework") });

		$(d.body).html(
			repl(
				`<div>
					<p>${__("Open Source Applications for the Web")}</p>
					<p><i class='fa fa-globe fa-fw'></i>
						${__("Website")}:
						<a href='https://ntsframework.com' target='_blank'>https://ntsframework.com</a></p>
					<p><i class='fa fa-github fa-fw'></i>
						${__("Source")}:
						<a href='https://github.com/nts' target='_blank'>https://github.com/nts</a></p>
					<p><i class='fa fa-graduation-cap fa-fw'></i>
						nts School: <a href='https://nts.school' target='_blank'>https://nts.school</a></p>
					<p><i class='fa fa-linkedin fa-fw'></i>
						Linkedin: <a href='https://linkedin.com/company/nts-tech' target='_blank'>https://linkedin.com/company/nts-tech</a></p>
					<p><i class='fa fa-twitter fa-fw'></i>
						Twitter: <a href='https://twitter.com/ntstech' target='_blank'>https://twitter.com/ntstech</a></p>
					<p><i class='fa fa-youtube fa-fw'></i>
						YouTube: <a href='https://www.youtube.com/@ntstech' target='_blank'>https://www.youtube.com/@ntstech</a></p>
					<hr>
					<h4>${__("Installed Apps")}</h4>
					<div id='about-app-versions'>${__("Loading versions...")}</div>
					<hr>
					<p class='text-muted'>${__("&copy; nts Technologies Pvt. Ltd. and contributors")} </p>
					</div>`,
				nts.app
			)
		);

		nts.ui.misc.about_dialog = d;

		nts.ui.misc.about_dialog.on_page_show = function () {
			if (!nts.versions) {
				nts.call({
					method: "nts.utils.change_log.get_versions",
					callback: function (r) {
						show_versions(r.message);
					},
				});
			} else {
				show_versions(nts.versions);
			}
		};

		var show_versions = function (versions) {
			var $wrap = $("#about-app-versions").empty();
			$.each(Object.keys(versions).sort(), function (i, key) {
				var v = versions[key];
				let text;
				if (v.branch) {
					text = $.format("<p><b>{0}:</b> v{1} ({2})<br></p>", [
						v.title,
						v.branch_version || v.version,
						v.branch,
					]);
				} else {
					text = $.format("<p><b>{0}:</b> v{1}<br></p>", [v.title, v.version]);
				}
				$(text).appendTo($wrap);
			});

			nts.versions = versions;
		};
	}

	nts.ui.misc.about_dialog.show();
};
