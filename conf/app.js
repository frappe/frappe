wn.app = {
	name: 'Yourapp',
	license: 'GNU/GPL - Usage Condition: All "yourapp" branding must be kept as it is',
	source: 'https://github.com/webnotes/yourapp',
	publisher: 'Your Company',
	copyright: '&copy; Your Company',
	version: window._version_number
}

// call startup when ready
$(document).bind('ready', function() {
	startup();
});

$(document).bind('toolbar_setup', function() {
	$('.brand').html('yourbrand\
		<i class="icon-home icon-white navbar-icon-home" ></i>');
});
