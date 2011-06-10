// short hand functions for setting up
// rich text editor tinymce
wn.ele.rich_text = {
	add_simple: function(ele, height) {
		if(ele.myid) {
			tinyMCE.execCommand( 'mceAddControl', true, ele.myid);
			return;
		}
		
		// no create
		ele.myid = wn.dom.set_unique_id(ele);
		$(ele).tinymce({
			// Location of TinyMCE script
			script_url : 'js/tiny_mce_33/tiny_mce.js',

			height: height ? height : '200px',
			
			// General options
		    theme : "advanced",
		    theme_advanced_buttons1 : "bold,italic,underline,separator,strikethrough,justifyleft,justifycenter,justifyright,justifyfull,bullist,numlist,outdent,indent,link,unlink,forecolor,backcolor,code,",
		    theme_advanced_buttons2 : "",
		    theme_advanced_buttons3 : "",
		    theme_advanced_toolbar_location : "top",
		    theme_advanced_toolbar_align : "left",
			theme_advanced_path : false,
			theme_advanced_resizing : false
		});		
	},
	
	remove: function(ele) {
		tinyMCE.execCommand( 'mceRemoveControl', true, ele.myid);
	},
	
	get_value: function(ele) {
		return tinymce.get(ele.myid).getContent();
	}
}