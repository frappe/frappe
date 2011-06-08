wn.widgets.follow = {
	followers: {},
	
	Follow: function(parent, dt, dn) {
		var me = this;
		this.wrapper = $a(parent, 'div', 'follower-wrapper');
		this.parent = parent;
		this.dt=dt; this.dn = dn;
		this.max_followers = 5;
		
		// load followers
		this.load_followers = function() {
			$c('webnotes.widgets.follow.load_followers', {dt: me.dt, dn: me.dn}, function(r,rt) {
				me.update_follow(r);
			})
		}

		// make body
		this.make_body = function() {
			this.wrapper.innerHTML = '';
			if(in_list(this.flist, user_fullname)) {
				this.btn = $btn(this.wrapper, 'Unfollow', this.unfollow)
			} else {
				this.btn = $btn(this.wrapper, '+ Follow', this.follow, {fontWeight: 'bold'}, 'green');	
			}
			this.invite_link = $ln(this.wrapper, 'Invite to follow', 
				function(ln) { me.invite() }, {marginLeft:'8px', fontSize:'11px'}
			);
			this.help_link = $ln(this.wrapper, '[?]', 
				function(ln) { msgprint('<b>What is follow?</b> When you follow something, you are kept updated \
				with all the events that happen around it. Much like Twitter or Quora') }, 
					{marginLeft:'8px', fontSize:'11px'}
			);
			this.show_followers();
		}

		// show followers
		this.show_followers = function() {
			var div = $a(this.wrapper, 'div', 'follower-list')
			var m = (this.flist.length > this.max_followers) ? this.max_followers : this.flist.length;
			var fl = []
			for(var i=0 ;i<m; i++) { 
				if(this.flist[i]==user_fullname) { fl.push('You'.bold()) }
				else { fl.push(this.flist[i]); }
			}
			if(fl.length)
				div.innerHTML = this.flist.length + ' people following this including ' + fl.join(', ')
			else
				div.innerHTML = 'Be the first one to follow'
		}
		
		// update
		this.update_follow = function(r) {
			var f = wn.widgets.follow.followers
			if(!f[r.dt]) f[r.dt] = {}
			f[r.dt][r.dn] = r.message;
			this.flist = r.message;
			this.make_body();
		}
		
		// follow
		this.follow = function() {
			$c('webnotes.widgets.follow.follow', {dt: me.dt, dn: me.dn, user: user}, function(r, rt) {
				me.update_follow(r);
			})
		}

		// unfollows
		this.unfollow = function() {
			$c('webnotes.widgets.follow.unfollow', {dt: me.dt, dn: me.dn, user: user}, function(r, rt) {
				me.update_follow(r);
			})
		}
		
		// invite
		this.invite = function() {
			if(!this.dialog) {
				this.dialog = new wn.widgets.Dialog({
					title:'Invite someone to follow',
					width:400,
					fields: [
						{fieldtype:'Link', fieldname:'user', label:'Select the user to who you want to invite', options:'Profile',reqd:1},
						{fieldtype:'Button', fieldname:'invite', label:'Invite'}
					]
				});
				this.dialog.make()
				this.dialog.fields_dict.user.get_query = function() {
					return 'SELECT tabProfile.name, tabProfile.first_name, tabProfile.last_name FROM tabProfile WHERE tabProfile.name LIKE "%s" OR tabProfile.first_name LIKE "%s" or tabProfile.last_name LIKE "%s" ORDER BY tabProfile.name ASC LIMIT 50'
				}
				this.dialog.fields_dict.invite.onclick = function() {
					var v = me.get_values();
					if(v) {
						var btn = me.dialog.fields_dict.invite;
						btn.set_working();
						$c('webnotes.widgets.follow.follow', {dt: me.dt, dn: me.dn, user: v.user}, 
						function(r, rt) {
							btn.done_working();
							me.update_follow(r);
						})
					}
				}
			}

			this.dialog.show();
		}
		
		// refresh
		this.refresh = function() {
			f = wn.widgets.follow;
			if(f[dt] && f[dt][dn]) {
				this.flist = f;
				this.make_body();
			}
			else this.load_followers();
		}
		
		this.refresh();
	}
}