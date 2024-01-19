// website_script.js
{% if javascript -%}{{ javascript }}{%- endif %}

{% if google_analytics_id -%}
// Google Analytics
(function(i,s,o,g,r,a,m){i['GoogleAnalyticsObject']=r;i[r]=i[r]||function(){
(i[r].q=i[r].q||[]).push(arguments)},i[r].l=1*new Date();a=s.createElement(o),
m=s.getElementsByTagName(o)[0];a.async=1;a.src=g;m.parentNode.insertBefore(a,m)
})(window,document,'script','//www.google-analytics.com/analytics.js','ga');

ga('create', '{{ google_analytics_id }}', 'auto');
{% if google_analytics_anonymize_ip %}
ga('set', 'anonymizeIp', true);
{% endif %}
ga('send', 'pageview');
// End Google Analytics
{%- endif %}

{% if enable_view_tracking %}

	window.frappe.track = (event_name) => { // TODO: add similar, optimized utility to frappe/builder
    		if (navigator.doNotTrack == 1 || window.is_404):
			return

		let browser = frappe.utils.get_browser();
		let query_params = frappe.utils.get_query_params();

		// Get visitor ID based on browser uniqueness
		import('https://openfpcdn.io/fingerprintjs/v3')
			.then(fingerprint_js => fingerprint_js.load())
			.then(fp => fp.get())
			.then(result => {
				frappe.call("frappe.website.log_event", {
					event_name: event_name,
					referrer: document.referrer,
					browser: browser.name,
					version: browser.version,
					user_tz: Intl.DateTimeFormat().resolvedOptions().timeZone,
					source: query_params.source,
					medium: query_params.medium,
					campaign: query_params.campaign,
					visitor_id: result.visitorId
				})
		})
	};

	frappe.ready(() => frappe.track("WebPageView"));
{% endif %}
