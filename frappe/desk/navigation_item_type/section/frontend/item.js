// The `Section` kind: a heading, and the rows filed under it.
//
// The one kind with no destination at all. Everything it does is structural — `parent_key`
// on other rows is what puts them here, and `collapsible` / `keep_closed` are what the
// rail reads to decide whether the heading discloses.
//
// A section carries an authored `key` like every other row (#42230), which is what lets a
// person's delta survive its label being changed. It is drawn only if it has children:
// the server drops an emptied one (#42231's cascade), and this returns a group either way
// rather than second-guessing a filter that has already run.

export default {
	render() {
		return { group: true };
	},
};
