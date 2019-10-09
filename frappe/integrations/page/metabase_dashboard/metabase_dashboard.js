frappe.pages['metabase-dashboard'].on_page_load = function(wrapper) {
	frappe.ui.make_app_page({
		parent: wrapper,
		title: 'Dashboard',
		single_column: true,
	});
	metabase.get_default(wrapper);
};

frappe.pages['metabase-dashboard'].on_page_show = function(wrapper) {
	const $pageAction = (
		$(wrapper)
			.find('div.page-head div.page-actions')
	);
	// remove change page-actions class
	$pageAction.removeClass('page-actions');

	// create dashboard selection field
	const selDashboard = frappe.ui.form.make_control({
		'parent': $pageAction,
		'df': {
			'fieldname': 'Dashboard',
			'fieldtype': 'Link',
			'options': 'Metabase Dashboard',
			'onchange': () => {
				const dashboardName = selDashboard.get_value();
				if (dashboardName) {
					metabase.loadDashboard(wrapper, dashboardName);
				}
			},
			'get_query': () => {
				return {
					'filters': {
						'is_active': 1,
					},
				};
			},
		},
		'render_input': true,
	});
	selDashboard.$wrapper.css('text-align', 'left');
};

const metabase = {};

metabase.get_default = (wrapper) => {
	frappe.call({
		'method': 'frappe.integrations.page.metabase_dashboard.get_default',
		'callback': function(r) {
			const dashbDetail = r.message;
			if (dashbDetail) {
				metabase.constDashboard(wrapper, dashbDetail);
			}
		},
	});
};

metabase.loadDashboard = (wrapper, dashboard) => {
	if (metabase.loadedDashboard != dashboard) {
		frappe.call({
			'method': 'frappe.integrations.page.metabase_dashboard.get_url',
			'args': {
				'dashboard': dashboard,
			},
			'callback': function(r) {
				const dashbDetail = r.message;
				if (dashbDetail) {
					metabase.constDashboard(wrapper, dashbDetail);
				}
			},
		});
	}
};

metabase.constDashboard = (wrapper, dashbDetail) => {
	// init variable
	const resizer = dashbDetail.resizer;
	const iframeUrl = dashbDetail.iframeUrl;
	const name = dashbDetail.name;
	// init page wrapper
	const pageContent = $(wrapper).find('div.layout-main-section');
	const pageTitle = $(wrapper).find('div.title-text');

	const createIframe = (page, resizer, iframeUrl) => {
		// clear dashboard
		page.empty();

		// prepare html
		const iframe = `
			<script src="${resizer}"></script>
			<iframe
				src="${iframeUrl}"
				frameborder="0"
				width=100%
				onload="iFrameResize({}, this)"
				allowtransparency
			></iframe>
		`;

		// append html to page
		$(iframe).appendTo(page);
	};

	if (iframeUrl && resizer) {
		// add dashboard
		createIframe(pageContent, resizer, iframeUrl);
		// cheange page title
		pageTitle.text(`${name} Dashboard`);
		// add variable
		metabase.loadedDashboard = name;
	}
};
