// Copyright (c) 2013, Web Notes Technologies Pvt. Ltd. and Contributors
// MIT License. See license.txt

module("Number Formatting");

test("#,###.##", function() {
	equal(format_number(100, "#,###.##"), "100.00");
	equal(format_number(1000, "#,###.##"), "1,000.00");
	equal(format_number(10000, "#,###.##"), "10,000.00");
	equal(format_number(1000000, "#,###.##"), "1,000,000.00");
	equal(format_number(1000000.345, "#,###.##"), "1,000,000.34");	
});

test("#,##,###.##", function() {
	equal(format_number(100, "#,##,###.##"), "100.00");
	equal(format_number(1000, "#,##,###.##"), "1,000.00");
	equal(format_number(10000, "#,##,###.##"), "10,000.00");
	equal(format_number(1000000, "#,##,###.##"), "10,00,000.00");
	equal(format_number(1000000.341, "#,##,###.##"), "10,00,000.34");	
	equal(format_number(10000000.341, "#,##,###.##"), "1,00,00,000.34");	
});

test("#.###,##", function() {
	equal(format_number(100, "#.###,##"), "100,00");
	equal(format_number(1000, "#.###,##"), "1.000,00");
	equal(format_number(10000, "#.###,##"), "10.000,00");
	equal(format_number(1000000, "#.###,##"), "1.000.000,00");
	equal(format_number(1000000.345, "#.###,##"), "1.000.000,34");
});

test("#.###", function() {
	equal(format_number(100, "#.###"), "100");
	equal(format_number(1000, "#.###"), "1.000");
	equal(format_number(10000, "#.###"), "10.000");
	equal(format_number(-100000, "#.###"), "-100.000");
	equal(format_number(1000000, "#.###"), "1.000.000");
	equal(format_number(1000000.345, "#.###"), "1.000.000");
});