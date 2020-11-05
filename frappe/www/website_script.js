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
	if (navigator.doNotTrack != 1 && !window.is_404) {
		frappe.ready(() => {
			let browser = frappe.utils.get_browser();
			frappe.call("frappe.website.doctype.web_page_view.web_page_view.make_view_log", {
				path: location.pathname,
				referrer: document.referrer,
				browser: browser.name,
				version: browser.version,
				url: location.origin,
				user_tz: Intl.DateTimeFormat().resolvedOptions().timeZone
			})
		})
	}
{% endif %}