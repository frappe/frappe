// Copyright (c) 2015, Frappe Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

QUnit.module("Number Formatting");

QUnit.test("#,###.##", function(assert) {
	assert.equal(format_number(100, "#,###.##"), "100.00");
	assert.equal(format_number(1000, "#,###.##"), "1,000.00");
	assert.equal(format_number(10000, "#,###.##"), "10,000.00");
	assert.equal(format_number(1000000, "#,###.##"), "1,000,000.00");
	assert.equal(format_number(1000000.345, "#,###.##"), "1,000,000.35");
});

QUnit.test("#,##,###.##", function(assert) {
	assert.equal(format_number(100, "#,##,###.##"), "100.00");
	assert.equal(format_number(1000, "#,##,###.##"), "1,000.00");
	assert.equal(format_number(10000, "#,##,###.##"), "10,000.00");
	assert.equal(format_number(1000000, "#,##,###.##"), "10,00,000.00");
	assert.equal(format_number(1000000.341, "#,##,###.##"), "10,00,000.34");
	assert.equal(format_number(10000000.341, "#,##,###.##"), "1,00,00,000.34");
});

QUnit.test("#.###,##", function(assert) {
	assert.equal(format_number(100, "#.###,##"), "100,00");
	assert.equal(format_number(1000, "#.###,##"), "1.000,00");
	assert.equal(format_number(10000, "#.###,##"), "10.000,00");
	assert.equal(format_number(1000000, "#.###,##"), "1.000.000,00");
	assert.equal(format_number(1000000.345, "#.###,##"), "1.000.000,35");
});

QUnit.test("#.###", function(assert) {
	assert.equal(format_number(100, "#.###"), "100");
	assert.equal(format_number(1000, "#.###"), "1.000");
	assert.equal(format_number(10000, "#.###"), "10.000");
	assert.equal(format_number(-100000, "#.###"), "-100.000");
	assert.equal(format_number(1000000, "#.###"), "1.000.000");
	assert.equal(format_number(1000000.345, "#.###"), "1.000.000");
});