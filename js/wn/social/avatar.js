// set user image
wn.social.avatars = {}
wn.social.avatar_queue = {};
wn.social.avatar_loading = [];

wn.social.set_avatar = function(img, username, get_latest, img_id) {
	function set_it(i) {
		if(wn.social.avatars[username]=='no_img_m')
			i.src = 'images/ui/no_img/no_img_m.gif';
		else if(wn.social.avatars[username]=='no_img_f')
			i.src = 'images/ui/no_img/no_img_f.gif'; // no image
		else {
			ac_id = locals['Control Panel']['Control Panel'].account_id;
			i.src = repl('cgi-bin/getfile.cgi?ac=%(ac)s&name=%(fn)s', {fn:wn.social.avatars[username], ac:ac_id});			
		}
	}

	// given
	if(img_id) {
		wn.social.avatars[username] = img_id;
		set_it(img);
		return;
	}
	
	// from dict or load
	if(wn.social.avatars[username] && !get_latest) {
		set_it(img);
	} else{
		// queue multiple request while loading
		if(in_list(wn.social.avatar_loading,username)) {
			if(!wn.social.avatar_queue[username]) 
				wn.social.avatar_queue[username] = [];
			wn.social.avatar_queue[username].push(img);
			return;
		}
		$c('webnotes.profile.get_user_img',{username:username},function(r,rt) { 
				delete wn.social.avatar_loading[wn.social.avatar_loading.indexOf(username)];
				wn.social.avatars[username] = r.message; 

				if(wn.social.avatar_queue[username]) {
					var q=wn.social.avatar_queue[username];
					for(var i in q) { set_it(q[i]); }
				}
				set_it(img); 
				
			}, null, 1);
		wn.social.avatar_loading.push(username);
	}

}
