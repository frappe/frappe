var chromedriver = require('chromedriver');
module.exports = {
	before: function (done) {
		chromedriver.start();
		done();
	},

	after: function (done) {
		chromedriver.stop();
		done();
	}
};