import ChartWidget from "../widgets/chart_widget";
import WidgetGroup from "../widgets/widget_group";

export default class Desk {
	constructor({ wrapper }) {
		this.wrapper = wrapper;
		this.make();
		window.desk = this;
	}

	make() {
		this.make_container();
		this.show_loading_state();
		this.fetch_desktop_settings().then(() => {
			this.make_sidebar();
			this.make_body();
			this.setup_events;
			this.hide_loading_state();
		});
	}

	make_container() {
		this.container = $(`<div class="desk-container row">
				<div class="desk-sidebar"></div>
				<div class="desk-body"></div>
			</div>`);

		this.container.appendTo(this.wrapper);
		this.sidebar = this.container.find(".desk-sidebar");
		this.body = this.container.find(".desk-body");
	}

	show_loading_state() {
		// Add skeleton
		let loading_sidebar = $(
			'<div class="skeleton skeleton-full" style="height: 90vh;"></div>'
		);
		let loading_body = $(
			`<div class="skeleton skeleton-full" style="height: 90vh;"></div>`
		);

		// Append skeleton to body
		loading_sidebar.appendTo(this.sidebar);
		loading_body.appendTo(this.body);
	}

	hide_loading_state() {
		// Remove all skeleton
		this.container.find(".skeleton").remove();
	}

	fetch_desktop_settings() {
		return frappe
			.call("frappe.desk.desktop.get_base_configuration_for_desk")
			.then(response => {
				if (response.message) {
					// console.log(response);
					this.desktop_settings = response.message;
				} else {
					frappe.throw({
						title: "Couldn't Load Desk",
						message:
							"Something went wrong while loading Desk. <b>Please relaod the page</b>. If the problem persists, contact the Administrator",
						indicator: "red",
						primary_action: {
							label: "Reload",
							action: () => location.reload()
						}
					});
				}
			});
	}

	make_sidebar() {
		const get_sidebar_item = function(item) {
			// let icon_class = item.icon ? item.icon : 'frapicon-dashboard'
			// let icon = `<i class="icon ${icon_class}"></i>`;
			// if (icon_class.includes("frapicon-")) {
			// 	icon = `<img class="icon" src="/assets/frappe/icons/${
			// 		icon_class
			// 	}.svg">`;
			// }

			return $(`<div href="#" class="sidebar-item ${
				item.selected ? "selected" : ""
			}">
					<span class="sidebar-item-title">${item.name}</span>
				</div>`);
		};

		this.desktop_settings.forEach((item, idx) => {
			if (idx == 0) {
				item.selected = true;
			}
			get_sidebar_item(item).appendTo(this.sidebar);
		});
	}

	make_body() {
		new DeskPage({
			container: this.body,
			page_name: "Accounts"
		});
	}

	setup_events() {}
}

class DeskPage {
	constructor({ container, page_name }) {
		this.container = container;
		this.page_name = page_name;
		window.desk_page = this;
		this.sections = {}
		this.make();
	}

	make() {
		// this.bootstrap()
		this.get_data().then(res => {
			this.data = res.message;
			this.make_charts()
			this.make_shortcuts()
			this.make_cards()
		})
	}

	get_data() {
		return frappe.call('frappe.desk.desktop.get_desktop_page', { page: 'CRM' } )
	}

	make_charts() {
		this.sections['charts'] = new WidgetGroup({
			title: `${this.page_name} Dashboard`,
			container: this.container,
			type: "chart",
			columns: 1,
			widgets: this.data.charts
		});
	}

	make_shortcuts() {
		console.log(this.data.shortcuts)
		this.sections['shortcuts'] = new WidgetGroup({
			title: `Your Shortcuts`,
			container: this.container,
			type: "bookmark",
			columns: 3,
			allow_sorting: 1,
			widgets: this.data.shortcuts
		});
	}

	make_cards() {
		// new WidgetGroup({
		// 	title: `${this.page_name} Dashboard`,
		// 	container: this.container,
		// 	type: "chart",
		// 	columns: 1,
		// 	widgets: [
		// 		{
		// 			label: "Incoming Bills (Purchase Invoice)",
		// 			options: {
		// 				chart_name: "Incoming Bills (Purchase Invoice)"
		// 			}
		// 		}
		// 	]
		// });

		// new WidgetGroup({
		// 	title: `Your shortcuts`,
		// 	container: this.container,
		// 	type: "bookmark",
		// 	columns: 3,
		// 	allow_sorting: 1,
		// 	widgets: [
		// 		{
		// 			label: "Customers",
		// 			options: {
		// 				color: "green",
		// 				count: 120,
		// 				format_string: "{} Active"
		// 			}
		// 		},
		// 		{
		// 			label: "Sales Invoice",
		// 			options: {
		// 				color: "red",
		// 				count: 14,
		// 				format_string: "{} Open"
		// 			}
		// 		},
		// 		{
		// 			label: "Accounts Receivable"
		// 		}
		// 	]
		// });

		new WidgetGroup({
			title: `Reports & Masters`,
			container: this.container,
			type: "links",
			columns: 3,
			allow_sorting: 1,
			widgets: [
				{
					label: "Accounts Receivable",
					links: [
						{
							type: "doctype",
							name: "Sales Invoice",
							description: "Bills raised to Customers.",
							onboard: 1,
							label: "Sales Invoice",
							count: 3350
						},
						{
							type: "doctype",
							name: "Customer",
							description: "Customer database.",
							onboard: 1,
							label: "Customer",
							count: 62218
						},
						{
							type: "doctype",
							name: "Payment Entry",
							description:
								"Bank/Cash transactions against party or for internal transfer",
							label: "Payment Entry"
						},
						{
							type: "doctype",
							name: "Payment Request",
							description: "Payment Request",
							label: "Payment Request"
						},
						{
							type: "report",
							name: "Accounts Receivable",
							doctype: "Sales Invoice",
							is_query_report: true,
							label: "Accounts Receivable",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							name: "Accounts Receivable Summary",
							doctype: "Sales Invoice",
							is_query_report: true,
							label: "Accounts Receivable Summary",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							name: "Sales Register",
							doctype: "Sales Invoice",
							is_query_report: true,
							label: "Sales Register",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							name: "Item-wise Sales Register",
							is_query_report: true,
							doctype: "Sales Invoice",
							label: "Item-wise Sales Register",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							name: "Ordered Items To Be Billed",
							is_query_report: true,
							doctype: "Sales Invoice",
							label: "Ordered Items To Be Billed",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							name: "Delivered Items To Be Billed",
							is_query_report: true,
							doctype: "Sales Invoice",
							label: "Delivered Items To Be Billed",
							dependencies: ["Sales Invoice"]
						}
					]
				},
				{
					label: "Accounts Payable",
					links: [
						{
							type: "doctype",
							name: "Purchase Invoice",
							description: "Bills raised by Suppliers.",
							onboard: 1,
							label: "Purchase Invoice",
							count: 3192
						},
						{
							type: "doctype",
							name: "Supplier",
							description: "Supplier database.",
							onboard: 1,
							label: "Supplier",
							count: 305
						},
						{
							type: "doctype",
							name: "Payment Entry",
							description:
								"Bank/Cash transactions against party or for internal transfer",
							label: "Payment Entry"
						},
						{
							type: "report",
							name: "Accounts Payable",
							doctype: "Purchase Invoice",
							is_query_report: true,
							label: "Accounts Payable",
							dependencies: ["Purchase Invoice"]
						},
						{
							type: "report",
							name: "Accounts Payable Summary",
							doctype: "Purchase Invoice",
							is_query_report: true,
							label: "Accounts Payable Summary",
							dependencies: ["Purchase Invoice"]
						},
						{
							type: "report",
							name: "Purchase Register",
							doctype: "Purchase Invoice",
							is_query_report: true,
							label: "Purchase Register",
							dependencies: ["Purchase Invoice"]
						},
						{
							type: "report",
							name: "Item-wise Purchase Register",
							is_query_report: true,
							doctype: "Purchase Invoice",
							label: "Item-wise Purchase Register",
							dependencies: ["Purchase Invoice"]
						},
						{
							type: "report",
							name: "Purchase Order Items To Be Billed",
							is_query_report: true,
							doctype: "Purchase Invoice",
							label: "Purchase Order Items To Be Billed",
							dependencies: ["Purchase Invoice"]
						},
						{
							type: "report",
							name: "Received Items To Be Billed",
							is_query_report: true,
							doctype: "Purchase Invoice",
							label: "Received Items To Be Billed",
							dependencies: ["Purchase Invoice"]
						}
					]
				},
				{
					label: "Accounting Masters",
					links: [
						{
							type: "doctype",
							name: "Company",
							description:
								"Company (not Customer or Supplier) master.",
							onboard: 1,
							label: "Company",
							count: 0
						},
						{
							type: "doctype",
							name: "Account",
							icon: "fa fa-sitemap",
							label: "Chart of Accounts",
							route: "#Tree/Account",
							description: "Tree of financial accounts.",
							onboard: 1,
							count: 460
						},
						{
							type: "doctype",
							name: "Accounts Settings",
							label: "Accounts Settings"
						},
						{
							type: "doctype",
							name: "Fiscal Year",
							description: "Financial / accounting year.",
							label: "Fiscal Year"
						},
						{
							type: "doctype",
							name: "Accounting Dimension",
							label: "Accounting Dimension"
						},
						{
							type: "doctype",
							name: "Finance Book",
							label: "Finance Book"
						},
						{
							type: "doctype",
							name: "Accounting Period",
							label: "Accounting Period"
						},
						{
							type: "doctype",
							name: "Payment Term",
							description: "Payment Terms based on conditions",
							label: "Payment Term"
						}
					]
				},
				{
					label: "Banking and Payments",
					links: [
						{
							type: "doctype",
							label: "Match Payments with Invoices",
							name: "Payment Reconciliation",
							description:
								"Match non-linked Invoices and Payments."
						},
						{
							type: "doctype",
							label: "Update Bank Transaction Dates",
							name: "Bank Reconciliation",
							description:
								"Update bank payment dates with journals."
						},
						{
							type: "doctype",
							label: "Invoice Discounting",
							name: "Invoice Discounting"
						},
						{
							type: "report",
							name: "Bank Reconciliation Statement",
							is_query_report: true,
							doctype: "Journal Entry",
							label: "Bank Reconciliation Statement",
							dependencies: ["Journal Entry"]
						},
						{
							type: "page",
							name: "bank-reconciliation",
							label: "Bank Reconciliation",
							icon: "fa fa-bar-chart"
						},
						{
							type: "report",
							name: "Bank Clearance Summary",
							is_query_report: true,
							doctype: "Journal Entry",
							label: "Bank Clearance Summary",
							dependencies: ["Journal Entry"]
						},
						{
							type: "doctype",
							name: "Bank Guarantee",
							label: "Bank Guarantee"
						},
						{
							type: "doctype",
							name: "Cheque Print Template",
							description: "Setup cheque dimensions for printing",
							label: "Cheque Print Template"
						}
					]
				},
				{
					label: "General Ledger",
					links: [
						{
							type: "doctype",
							name: "Journal Entry",
							description: "Accounting journal entries.",
							label: "Journal Entry"
						},
						{
							type: "report",
							name: "General Ledger",
							doctype: "GL Entry",
							is_query_report: true,
							label: "General Ledger",
							dependencies: ["GL Entry"]
						},
						{
							type: "report",
							name: "Customer Ledger Summary",
							doctype: "Sales Invoice",
							is_query_report: true,
							label: "Customer Ledger Summary",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							name: "Supplier Ledger Summary",
							doctype: "Sales Invoice",
							is_query_report: true,
							label: "Supplier Ledger Summary",
							dependencies: ["Sales Invoice"]
						}
					]
				},
				{
					label: "Taxes",
					links: [
						{
							type: "doctype",
							name: "Sales Taxes and Charges Template",
							description:
								"Tax template for selling transactions.",
							label: "Sales Taxes and Charges Template"
						},
						{
							type: "doctype",
							name: "Purchase Taxes and Charges Template",
							description:
								"Tax template for buying transactions.",
							label: "Purchase Taxes and Charges Template"
						},
						{
							type: "doctype",
							name: "Item Tax Template",
							description: "Tax template for item tax rates.",
							label: "Item Tax Template"
						},
						{
							type: "doctype",
							name: "Tax Category",
							description:
								"Tax Category for overriding tax rates.",
							label: "Tax Category"
						},
						{
							type: "doctype",
							name: "Tax Rule",
							description: "Tax Rule for transactions.",
							label: "Tax Rule"
						},
						{
							type: "doctype",
							name: "Tax Withholding Category",
							description:
								"Tax Withholding rates to be applied on transactions.",
							label: "Tax Withholding Category"
						}
					]
				},
				{
					label: "Cost Center and Budgeting",
					links: [
						{
							type: "doctype",
							name: "Cost Center",
							icon: "fa fa-sitemap",
							label: "Chart of Cost Centers",
							route: "#Tree/Cost Center",
							description: "Tree of financial Cost Centers."
						},
						{
							type: "doctype",
							name: "Budget",
							description: "Define budget for a financial year.",
							label: "Budget"
						},
						{
							type: "doctype",
							name: "Accounting Dimension",
							label: "Accounting Dimension"
						},
						{
							type: "report",
							name: "Budget Variance Report",
							is_query_report: true,
							doctype: "Cost Center",
							label: "Budget Variance Report",
							dependencies: ["Cost Center"]
						},
						{
							type: "doctype",
							name: "Monthly Distribution",
							description:
								"Seasonality for setting budgets, targets etc.",
							label: "Monthly Distribution"
						}
					]
				},
				{
					label: "Financial Statements",
					links: [
						{
							type: "report",
							name: "Trial Balance",
							doctype: "GL Entry",
							is_query_report: true,
							label: "Trial Balance",
							dependencies: ["GL Entry"]
						},
						{
							type: "report",
							name: "Profit and Loss Statement",
							doctype: "GL Entry",
							is_query_report: true,
							label: "Profit and Loss Statement",
							dependencies: ["GL Entry"]
						},
						{
							type: "report",
							name: "Balance Sheet",
							doctype: "GL Entry",
							is_query_report: true,
							label: "Balance Sheet",
							dependencies: ["GL Entry"]
						},
						{
							type: "report",
							name: "Cash Flow",
							doctype: "GL Entry",
							is_query_report: true,
							label: "Cash Flow",
							dependencies: ["GL Entry"]
						},
						{
							type: "report",
							name: "Consolidated Financial Statement",
							doctype: "GL Entry",
							is_query_report: true,
							label: "Consolidated Financial Statement",
							dependencies: ["GL Entry"]
						}
					]
				},
				{
					label: "Opening and Closing",
					links: [
						{
							type: "doctype",
							name: "Opening Invoice Creation Tool",
							label: "Opening Invoice Creation Tool"
						},
						{
							type: "doctype",
							name: "Chart of Accounts Importer",
							label: "Chart of Accounts Importer"
						},
						{
							type: "doctype",
							name: "Period Closing Voucher",
							description:
								"Close Balance Sheet and book Profit or Loss.",
							label: "Period Closing Voucher"
						}
					]
				},
				{
					label: "Goods and Services Tax (GST India)",
					links: [
						{
							type: "doctype",
							name: "GST Settings",
							label: "GST Settings"
						},
						{
							type: "doctype",
							name: "GST HSN Code",
							label: "GST HSN Code"
						},
						{
							type: "report",
							name: "GSTR-1",
							is_query_report: true,
							label: "GSTR-1"
						},
						{
							type: "report",
							name: "GSTR-2",
							is_query_report: true,
							label: "GSTR-2"
						},
						{
							type: "doctype",
							name: "GSTR 3B Report",
							label: "GSTR 3B Report"
						},
						{
							type: "report",
							name: "GST Sales Register",
							is_query_report: true,
							label: "GST Sales Register"
						},
						{
							type: "report",
							name: "GST Purchase Register",
							is_query_report: true,
							label: "GST Purchase Register"
						},
						{
							type: "report",
							name: "GST Itemised Sales Register",
							is_query_report: true,
							label: "GST Itemised Sales Register"
						},
						{
							type: "report",
							name: "GST Itemised Purchase Register",
							is_query_report: true,
							label: "GST Itemised Purchase Register"
						},
						{
							type: "doctype",
							name: "C-Form",
							description: "C-Form records",
							country: "India",
							label: "C-Form"
						}
					]
				},
				{
					label: "Multi Currency",
					links: [
						{
							type: "doctype",
							name: "Currency",
							description: "Enable / disable currencies.",
							label: "Currency"
						},
						{
							type: "doctype",
							name: "Currency Exchange",
							description: "Currency exchange rate master.",
							label: "Currency Exchange"
						},
						{
							type: "doctype",
							name: "Exchange Rate Revaluation",
							description: "Exchange Rate Revaluation master.",
							label: "Exchange Rate Revaluation"
						}
					]
				},
				{
					label: "Settings",
					icon: "fa fa-cog",
					links: [
						{
							type: "doctype",
							name: "Payment Gateway Account",
							description: "Setup Gateway accounts.",
							label: "Payment Gateway Account"
						},
						{
							type: "doctype",
							name: "Terms and Conditions",
							label: "Terms and Conditions Template",
							description: "Template of terms or contract."
						},
						{
							type: "doctype",
							name: "Mode of Payment",
							description: "e.g. Bank, Cash, Credit Card",
							label: "Mode of Payment"
						}
					]
				},
				{
					label: "Subscription Management",
					links: [
						{
							type: "doctype",
							name: "Subscriber",
							label: "Subscriber"
						},
						{
							type: "doctype",
							name: "Subscription Plan",
							label: "Subscription Plan"
						},
						{
							type: "doctype",
							name: "Subscription",
							label: "Subscription"
						},
						{
							type: "doctype",
							name: "Subscription Settings",
							label: "Subscription Settings"
						}
					]
				},
				{
					label: "Bank Statement",
					links: [
						{
							type: "doctype",
							label: "Bank",
							name: "Bank"
						},
						{
							type: "doctype",
							label: "Bank Account",
							name: "Bank Account"
						},
						{
							type: "doctype",
							name: "Bank Statement Transaction Entry",
							label: "Bank Statement Transaction Entry"
						},
						{
							type: "doctype",
							label: "Bank Statement Settings",
							name: "Bank Statement Settings"
						}
					]
				},
				{
					label: "Profitability",
					links: [
						{
							type: "report",
							name: "Gross Profit",
							doctype: "Sales Invoice",
							is_query_report: true,
							label: "Gross Profit",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							name: "Profitability Analysis",
							doctype: "GL Entry",
							is_query_report: true,
							label: "Profitability Analysis",
							dependencies: ["GL Entry"]
						},
						{
							type: "report",
							name: "Sales Invoice Trends",
							is_query_report: true,
							doctype: "Sales Invoice",
							label: "Sales Invoice Trends",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							name: "Purchase Invoice Trends",
							is_query_report: true,
							doctype: "Purchase Invoice",
							label: "Purchase Invoice Trends",
							dependencies: ["Purchase Invoice"]
						}
					]
				},
				{
					label: "Reports",
					icon: "fa fa-table",
					links: [
						{
							type: "report",
							name: "Trial Balance for Party",
							doctype: "GL Entry",
							is_query_report: true,
							label: "Trial Balance for Party",
							dependencies: ["GL Entry"]
						},
						{
							type: "report",
							name: "Payment Period Based On Invoice Date",
							is_query_report: true,
							doctype: "Journal Entry",
							label: "Payment Period Based On Invoice Date",
							dependencies: ["Journal Entry"]
						},
						{
							type: "report",
							name: "Sales Partners Commission",
							is_query_report: true,
							doctype: "Sales Invoice",
							label: "Sales Partners Commission",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							is_query_report: true,
							name: "Customer Credit Balance",
							doctype: "Customer",
							label: "Customer Credit Balance",
							dependencies: ["Customer"]
						},
						{
							type: "report",
							is_query_report: true,
							name: "Sales Payment Summary",
							doctype: "Sales Invoice",
							label: "Sales Payment Summary",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							is_query_report: true,
							name: "Address And Contacts",
							doctype: "Address",
							label: "Address And Contacts",
							dependencies: ["Address"]
						}
					]
				},
				{
					label: "Share Management",
					icon: "fa fa-microchip ",
					links: [
						{
							type: "doctype",
							name: "Shareholder",
							description:
								"List of available Shareholders with folio numbers",
							label: "Shareholder"
						},
						{
							type: "doctype",
							name: "Share Transfer",
							description: "List of all share transactions",
							label: "Share Transfer"
						},
						{
							type: "report",
							name: "Share Ledger",
							doctype: "Share Transfer",
							is_query_report: true,
							label: "Share Ledger",
							dependencies: ["Share Transfer"],
							incomplete_dependencies: ["Share Transfer"]
						},
						{
							type: "report",
							name: "Share Balance",
							doctype: "Share Transfer",
							is_query_report: true,
							label: "Share Balance",
							dependencies: ["Share Transfer"],
							incomplete_dependencies: ["Share Transfer"]
						}
					]
				},
				{
					label: "Custom Reports",
					icon: "fa fa-list-alt",
					links: [
						{
							type: "report",
							doctype: "Sales Invoice",
							is_query_report: 0,
							label: "Account Expiry",
							name: "Account Expiry",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							doctype: "Sales Invoice",
							is_query_report: 0,
							label: "Active Customers",
							name: "Active Customers",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							doctype: "Journal Entry",
							is_query_report: 0,
							label:
								"Credit Card Expenses directly booked via Journal Entry",
							name:
								"Credit Card Expenses directly booked via Journal Entry",
							dependencies: ["Journal Entry"]
						},
						{
							type: "report",
							doctype: "Sales Invoice",
							is_query_report: 0,
							label: "Development Support",
							name: "Development Support",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							doctype: "Sales Invoice",
							is_query_report: 0,
							label: "ERPNext Commercial Support",
							name: "ERPNext Commercial Support",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							doctype: "Sales Invoice",
							is_query_report: 1,
							label: "Monthly Recurring Revenue",
							name: "Monthly Recurring Revenue",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							doctype: "Sales Invoice",
							is_query_report: 0,
							label: "Monthly Sales Invoice",
							name: "Monthly Sales Invoice",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							doctype: "GL Entry",
							is_query_report: 0,
							label: "Payments Received",
							name: "Payments Received",
							dependencies: ["GL Entry"]
						},
						{
							type: "report",
							doctype: "Sales Invoice",
							is_query_report: 0,
							label: "Sales Report",
							name: "Sales Report",
							dependencies: ["Sales Invoice"]
						},
						{
							type: "report",
							doctype: "Sales Invoice",
							is_query_report: 0,
							label: "Service Tax Report",
							name: "Service Tax Report",
							dependencies: ["Sales Invoice"]
						}
					]
				}
			]
		});
	}
}
