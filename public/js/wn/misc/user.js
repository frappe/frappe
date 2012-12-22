// misc user functions

wn.user_info = function(uid) {
	var def = {
		'fullname':uid, 
		'image': 'lib/images/ui/avatar.png'
	}
	if(!wn.boot.user_info) return def
	if(!wn.boot.user_info[uid]) return def
	if(!wn.boot.user_info[uid].fullname)
		wn.boot.user_info[uid].fullname = uid;
	if(!wn.boot.user_info[uid].image)
		wn.boot.user_info[uid].image = def.image;
	return wn.boot.user_info[uid];
}

wn.avatar = function(user, large, title) {
	var image = wn.utils.get_file_link(wn.user_info(user).image);
	var to_size = large ? 72 : 30;
	if(!title) title = wn.user_info(user).fullname;

	return repl('<span class="avatar" title="%(title)s" style="width: %(len)s; \
		height: %(len)s; border-radius: %(len)s; overflow: hidden;">\
		<img src="%(image)s"></span>', {
			image: image,
			len: to_size + "px",
			title: title
		});	
}

wn.provide('wn.user');

$.extend(wn.user, {
	name: (wn.boot ? wn.boot.profile.name : 'Guest'),
	has_role: function(rl) {
		if(typeof rl=='string') 
			rl = [rl];
		for(var i in rl) {
			if((wn.boot ? wn.boot.profile.roles : ['Guest']).indexOf(rl[i])!=-1)
				return true;
		}
	},
	set_default: function(key, value, callback) {
		if(typeof value=="string")
			value = JSON.stringify(value);
			
		wn.boot.profile.defaults[key] = value;
		wn.call({
			method: "webnotes.client.set_default",
			args: {
				key: key,
				value: value
			},
			callback: callback || function(r) {}
		});
	},
	get_default: function(key) {
		var value = wn.boot.profile.defaults[key];
		if(value) {
			try {
				return JSON.parse(value)
			} catch(e) {
				return value;
			}			
		}
	},
	get_desktop_items: function() {
		var user_list = wn.user.get_default("_desktop_items");
		if(user_list && user_list.length)
			return user_list;
		else
			return wn.boot.modules_list;
	},
	is_report_manager: function() {
		return wn.user.has_role(['Administrator', 'System Manager', 'Report Manager']);
	}
})

// wn.session_alive is true if user shows mouse movement in 30 seconds

wn.session_alive = true;
$(document).bind('mousemove', function() {
	wn.session_alive = true;
	if(wn.session_alive_timeout) 
		clearTimeout(wn.session_alive_timeout);
	wn.session_alive_timeout = setTimeout('wn.session_alive=false;', 30000);
})