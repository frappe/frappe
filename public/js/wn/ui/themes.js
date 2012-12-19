// for license information please see license.txt

wn.provide("wn.ui");

wn.ui.set_user_background = function(src) {
	set_style(repl('#body_div { background: url("files/%(src)s") repeat fixed;}',
		{src:src}))
}

wn.ui.themes = {
	"Default": {
		sidebar: "#f2f2f2",
		titlebar: "#d2d2d2",
		toolbar: "#e9e9e9"
	},
	Desert: {
		sidebar: "#FFFDF7",
		titlebar: "#DAD4C2",
		toolbar: "#FAF6E9"
	},
	Tropic: {
		sidebar: "#FAFFF7",
		toolbar: "#EEFAE9",
		titlebar: "#D7ECD1"
	},
	Sky: {
		sidebar: "#F7FFFE",
		toolbar: "#E9F9FA",
		titlebar: "#D7F5F7"
	},
	Snow: {
		sidebar: "#fff",
		titlebar: "#fff",
		toolbar: "#fff"
	},
	Sunny: {
		sidebar: "#FFFFEF",
		titlebar: "#FFFDCA",
		toolbar: "lightYellow"
	},
	Floral: {
		sidebar: "#FFF7F7",
		titlebar: "#F7CBCB",
		toolbar: "#FAE9EA"		
	},
	Ocean: {
		sidebar: "#F2FFFE",
		titlebar: "#8ACFC7",
		toolbar: "#C3F3EE"
	}
}

wn.ui.set_theme = function(theme) {
	var t = wn.ui.themes[theme];
	t.title_gradient = wn.get_gradient_css(t.titlebar);
	var css = repl(".layout-wrapper-background { \
		background-color: %(sidebar)s !important; }\
	.appframe-toolbar { \
		background-color: %(toolbar)s !important; }\
	.appframe-titlebar { \
		%(title_gradient)s \
	}", t);
	wn.dom.set_style(css);
}