export default class Blank {
	static get toolbox() {
		return {
			title: 'Blank',
			icon: '<svg width="18" height="18" viewBox="0 0 400 400"><path d="M377.87 24.126C361.786 8.042 342.417 0 319.769 0H82.227C59.579 0 40.211 8.042 24.125 24.126 8.044 40.212.002 59.576.002 82.228v237.543c0 22.647 8.042 42.014 24.123 58.101 16.086 16.085 35.454 24.127 58.102 24.127h237.542c22.648 0 42.011-8.042 58.102-24.127 16.085-16.087 24.126-35.453 24.126-58.101V82.228c-.004-22.648-8.046-42.016-24.127-58.102zm-12.422 295.645c0 12.559-4.47 23.314-13.415 32.264-8.945 8.945-19.698 13.411-32.265 13.411H82.227c-12.563 0-23.317-4.466-32.264-13.411-8.945-8.949-13.418-19.705-13.418-32.264V82.228c0-12.562 4.473-23.316 13.418-32.264 8.947-8.946 19.701-13.418 32.264-13.418h237.542c12.566 0 23.319 4.473 32.265 13.418 8.945 8.947 13.415 19.701 13.415 32.264v237.543h-.001z"/></svg>'
		};
	}

	static get isReadOnlySupported() {
		return true;
	}

	constructor({data, api, config, readOnly}) {
		this.data = data;
		this.api = api;
		this.config = config;
		this.readOnly = readOnly;
		this.col = this.data.col ? this.data.col : "12";
		this.pt = this.data.pt ? this.data.pt : "0";
		this.pr = this.data.pr ? this.data.pr : "0";
		this.pb = this.data.pb ? this.data.pb : "0";
		this.pl = this.data.pl ? this.data.pl : "0";
	}

	render() {
		this.wrapper = document.createElement('div');
		if (!this.readOnly) {
			this.wrapper.innerText = 'Blank';
			this.wrapper.classList.add('widget', 'new-widget');
			this.wrapper.style.minHeight = 50 + 'px';
		}
		return this.wrapper;
	}

	save() {
		return {
			col: this._getCol(),
			pt: this._getPadding("t"),
			pr: this._getPadding("r"),
			pb: this._getPadding("b"),
			pl: this._getPadding("l")
		};
	}

	rendered() {
		var e = this.wrapper.parentNode.parentNode;
		e.classList.add("col-" + this.col);
		e.classList.add("pt-" + this.pt);
		e.classList.add("pr-" + this.pr);
		e.classList.add("pb-" + this.pb);
		e.classList.add("pl-" + this.pl);
	}

	_getCol() {
		var e = 12;
		var t = "col-12";
		var n = this.wrapper.parentNode.parentNode;
		var r = new RegExp(/\bcol-.+?\b/, "g");
		if (n.className.match(r)) {
			n.classList.forEach(function (e) {
				e.match(r) && (t = e);
			});
			var a = t.split("-");
			e = parseInt(a[1]);
		}
		return e;
	}

	_getPadding() {
		var e = arguments.length > 0 && void 0 !== arguments[0] ? arguments[0] : "l";
		var t = 0;
		var n = "p" + e + "-0";
		var r = this.wrapper.parentNode.parentNode;
		var a = new RegExp(/\pl-.+?\b/, "g");
		var i = new RegExp(/\pr-.+?\b/, "g");
		var o = new RegExp(/\pt-.+?\b/, "g");
		var c = new RegExp(/\pb-.+?\b/, "g");
		if ("l" == e) {
			if (r.className.match(a)) {
				r.classList.forEach(function (e) {
					e.match(a) && (n = e);
				});
				var s = n.split("-");
				t = parseInt(s[1]);
			}
		} else if ("r" == e) {
			if (r.className.match(i)) {
				r.classList.forEach(function (e) {
					e.match(i) && (n = e);
				});
				var l = n.split("-");
				t = parseInt(l[1]);
			}
		} else if ("t" == e) {
			if (r.className.match(o)) {
				r.classList.forEach(function (e) {
					e.match(o) && (n = e);
				});
				var u = n.split("-");
				t = parseInt(u[1]);
			}
		} else if ("b" == e && r.className.match(c)) {
			r.classList.forEach(function (e) {
				e.match(c) && (n = e);
			});
			var p = n.split("-");
			t = parseInt(p[1]);
		}
		return t;
	}
}