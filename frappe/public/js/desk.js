// import "../js/lib/datepicker/datepicker.min.css";
// import "../js/lib/awesomplete/awesomplete.css";
// import "../js/lib/summernote/summernote.css";
// import "../js/lib/leaflet/leaflet.css";
// import "../js/lib/leaflet/leaflet.draw.css";
// import "../js/lib/leaflet/L.Control.Locate.css";
// import "../js/lib/leaflet/easy-button.css";
import "../css/bootstrap.css";
import "../css/font-awesome.css";
import "../css/octicons/octicons.css";

import '../less/desk.less';
import "../less/indicator.less";
import "../less/avatar.less";
import "../less/navbar.less";
import "../less/sidebar.less";
import "../less/page.less";
import "../less/desktop.less";
import "../less/mobile.less";
// import "../less/form.less";
// import "../less/tree.less";
// import "../less/kanban.less";
// import "../less/controls.less";

// import 'sortablejs';

import './frappe/class';
import './frappe/provide';
import './frappe/assets';
import './frappe/dom';
import './frappe/format';
import './frappe/ui/messages';
import './frappe/ui/keyboard';
import './frappe/translate';

import './frappe/request';
import './frappe/socketio_client';
import './frappe/router';
import './frappe/defaults';
import './utils/microtemplate';

import './legacy/globals';
import './legacy/datatype';
import './legacy/dom';
import './legacy/handler';

import './frappe/ui/page';
// import './frappe/ui/dialog';
import './frappe/ui/app_icon';

import './frappe/db';
import './frappe/model';

import './frappe/misc/user';
import './frappe/misc/common';
// import './frappe/misc/pretty_date';
import './frappe/misc/utils';

import './frappe/misc/tools';
import './frappe/misc/datetime';
import './frappe/misc/number_format';
// import './frappe/misc/help';
// import './frappe/misc/help_links';
// import './frappe/misc/address_and_contact';
// import './frappe/misc/preview_email';

import './frappe/views/container';
import './frappe/views/breadcrumbs';
import './frappe/views/factory';
import './frappe/views/pageview';

import './frappe/ui/toolbar';

import './frappe/desk';

frappe.start_app = function() {
	if(!frappe.Application)
		return;
	frappe.assets.check();
	frappe.provide('frappe.app');
	frappe.app = new frappe.Application();
};

$(document).ready(function() {
	if(!frappe.utils.supportsES6) {
		frappe.msgprint({
			indicator: 'red',
			title: __('Browser not supported'),
			message: __('Some of the features might not work in your browser. Please update your browser to the latest version.')
		});
	}

	frappe.start_app();
});
