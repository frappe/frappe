-- Core Elements to install WNFramework
-- To be called from install.py


--
-- Table structure for table "tabDocField"
--

DROP TABLE IF EXISTS "tabDocField";
CREATE TABLE "tabDocField" (
  "name" varchar(255) NOT NULL,
  "creation" timestamp(6) DEFAULT NULL,
  "modified" timestamp(6) DEFAULT NULL,
  "modified_by" varchar(255) DEFAULT NULL,
  "owner" varchar(255) DEFAULT NULL,
  "docstatus" smallint NOT NULL DEFAULT 0,
  "parent" varchar(255) DEFAULT NULL,
  "parentfield" varchar(255) DEFAULT NULL,
  "parenttype" varchar(255) DEFAULT NULL,
  "idx" bigint NOT NULL DEFAULT 0,
  "fieldname" varchar(255) DEFAULT NULL,
  "label" varchar(255) DEFAULT NULL,
  "oldfieldname" varchar(255) DEFAULT NULL,
  "fieldtype" varchar(255) DEFAULT NULL,
  "oldfieldtype" varchar(255) DEFAULT NULL,
  "options" text,
  "search_index" smallint NOT NULL DEFAULT 0,
  "hidden" smallint NOT NULL DEFAULT 0,
  "set_only_once" smallint NOT NULL DEFAULT 0,
  "show_dashboard" smallint NOT NULL DEFAULT 0,
  "allow_in_quick_entry" smallint NOT NULL DEFAULT 0,
  "print_hide" smallint NOT NULL DEFAULT 0,
  "report_hide" smallint NOT NULL DEFAULT 0,
  "reqd" smallint NOT NULL DEFAULT 0,
  "bold" smallint NOT NULL DEFAULT 0,
  "in_global_search" smallint NOT NULL DEFAULT 0,
  "collapsible" smallint NOT NULL DEFAULT 0,
  "unique" smallint NOT NULL DEFAULT 0,
  "no_copy" smallint NOT NULL DEFAULT 0,
  "allow_on_submit" smallint NOT NULL DEFAULT 0,
  "show_preview_popup" smallint NOT NULL DEFAULT 0,
  "trigger" varchar(255) DEFAULT NULL,
  "collapsible_depends_on" text,
  "mandatory_depends_on" text,
  "read_only_depends_on" text,
  "depends_on" text,
  "permlevel" bigint NOT NULL DEFAULT 0,
  "ignore_user_permissions" smallint NOT NULL DEFAULT 0,
  "width" varchar(255) DEFAULT NULL,
  "print_width" varchar(255) DEFAULT NULL,
  "columns" bigint NOT NULL DEFAULT 0,
  "default" text,
  "description" text,
  "in_list_view" smallint NOT NULL DEFAULT 0,
  "fetch_if_empty" smallint NOT NULL DEFAULT 0,
  "in_filter" smallint NOT NULL DEFAULT 0,
  "remember_last_selected_value" smallint NOT NULL DEFAULT 0,
  "ignore_xss_filter" smallint NOT NULL DEFAULT 0,
  "print_hide_if_no_value" smallint NOT NULL DEFAULT 0,
  "allow_bulk_edit" smallint NOT NULL DEFAULT 0,
  "in_standard_filter" smallint NOT NULL DEFAULT 0,
  "in_preview" smallint NOT NULL DEFAULT 0,
  "read_only" smallint NOT NULL DEFAULT 0,
  "precision" varchar(255) DEFAULT NULL,
  "max_height" varchar(10) DEFAULT NULL,
  "length" bigint NOT NULL DEFAULT 0,
  "translatable" smallint NOT NULL DEFAULT 0,
  "hide_border" smallint NOT NULL DEFAULT 0,
  "hide_days" smallint NOT NULL DEFAULT 0,
  "hide_seconds" smallint NOT NULL DEFAULT 0,
  PRIMARY KEY ("name")
) ;

create index on "tabDocField" ("parent");
create index on "tabDocField" ("label");
create index on "tabDocField" ("fieldtype");
create index on "tabDocField" ("fieldname");

--
-- Table structure for table "tabDocPerm"
--

DROP TABLE IF EXISTS "tabDocPerm";
CREATE TABLE "tabDocPerm" (
  "name" varchar(255) NOT NULL,
  "creation" timestamp(6) DEFAULT NULL,
  "modified" timestamp(6) DEFAULT NULL,
  "modified_by" varchar(255) DEFAULT NULL,
  "owner" varchar(255) DEFAULT NULL,
  "docstatus" smallint NOT NULL DEFAULT 0,
  "parent" varchar(255) DEFAULT NULL,
  "parentfield" varchar(255) DEFAULT NULL,
  "parenttype" varchar(255) DEFAULT NULL,
  "idx" bigint NOT NULL DEFAULT 0,
  "permlevel" bigint DEFAULT '0',
  "role" varchar(255) DEFAULT NULL,
  "match" varchar(255) DEFAULT NULL,
  "read" smallint NOT NULL DEFAULT 1,
  "write" smallint NOT NULL DEFAULT 1,
  "create" smallint NOT NULL DEFAULT 1,
  "submit" smallint NOT NULL DEFAULT 0,
  "cancel" smallint NOT NULL DEFAULT 0,
  "delete" smallint NOT NULL DEFAULT 1,
  "amend" smallint NOT NULL DEFAULT 0,
  "report" smallint NOT NULL DEFAULT 1,
  "export" smallint NOT NULL DEFAULT 1,
  "import" smallint NOT NULL DEFAULT 0,
  "share" smallint NOT NULL DEFAULT 1,
  "print" smallint NOT NULL DEFAULT 1,
  "email" smallint NOT NULL DEFAULT 1,
  PRIMARY KEY ("name")
) ;

create index on "tabDocPerm" ("parent");

--
-- Table structure for table "tabDocType Action"
--

DROP TABLE IF EXISTS "tabDocType Action";
CREATE TABLE "tabDocType Action" (
  "name" varchar(255) NOT NULL,
  "creation" timestamp(6) DEFAULT NULL,
  "modified" timestamp(6) DEFAULT NULL,
  "modified_by" varchar(255) DEFAULT NULL,
  "owner" varchar(255) DEFAULT NULL,
  "docstatus" smallint NOT NULL DEFAULT 0,
  "parent" varchar(255) DEFAULT NULL,
  "parentfield" varchar(255) DEFAULT NULL,
  "parenttype" varchar(255) DEFAULT NULL,
  "idx" bigint NOT NULL DEFAULT 0,
  "label" varchar(140) NOT NULL,
  "group" text DEFAULT NULL,
  "action_type" varchar(140) NOT NULL,
  "action" varchar(140) NOT NULL,
  PRIMARY KEY ("name")
) ;

create index on "tabDocType Action" ("parent");

--
-- Table structure for table "tabDocType Link"
--

DROP TABLE IF EXISTS "tabDocType Link";
CREATE TABLE "tabDocType Link" (
  "name" varchar(255) NOT NULL,
  "creation" timestamp(6) DEFAULT NULL,
  "modified" timestamp(6) DEFAULT NULL,
  "modified_by" varchar(255) DEFAULT NULL,
  "owner" varchar(255) DEFAULT NULL,
  "docstatus" smallint NOT NULL DEFAULT 0,
  "parent" varchar(255) DEFAULT NULL,
  "parentfield" varchar(255) DEFAULT NULL,
  "parenttype" varchar(255) DEFAULT NULL,
  "idx" bigint NOT NULL DEFAULT 0,
  "label" varchar(140) DEFAULT NULL,
  "group" varchar(140) DEFAULT NULL,
  "link_doctype" varchar(140) NOT NULL,
  "link_fieldname" varchar(140) NOT NULL,
  PRIMARY KEY ("name")
) ;

create index on "tabDocType Link" ("parent");


--
-- Table structure for table "tabDocType"
--

DROP TABLE IF EXISTS "tabDocType";
CREATE TABLE "tabDocType" (
  "name" varchar(255) NOT NULL,
  "creation" timestamp(6) DEFAULT NULL,
  "modified" timestamp(6) DEFAULT NULL,
  "modified_by" varchar(255) DEFAULT NULL,
  "owner" varchar(255) DEFAULT NULL,
  "docstatus" smallint NOT NULL DEFAULT 0,
  "idx" bigint NOT NULL DEFAULT 0,
  "search_fields" varchar(255) DEFAULT NULL,
  "issingle" smallint NOT NULL DEFAULT 0,
  "is_virtual" smallint NOT NULL DEFAULT 0,
  "is_tree" smallint NOT NULL DEFAULT 0,
  "istable" smallint NOT NULL DEFAULT 0,
  "editable_grid" smallint NOT NULL DEFAULT 1,
  "track_changes" smallint NOT NULL DEFAULT 0,
  "module" varchar(255) DEFAULT NULL,
  "restrict_to_domain" varchar(255) DEFAULT NULL,
  "app" varchar(255) DEFAULT NULL,
  "autoname" varchar(255) DEFAULT NULL,
  "naming_rule" varchar(40) DEFAULT NULL,
  "title_field" varchar(255) DEFAULT NULL,
  "image_field" varchar(255) DEFAULT NULL,
  "timeline_field" varchar(255) DEFAULT NULL,
  "sort_field" varchar(255) DEFAULT NULL,
  "sort_order" varchar(255) DEFAULT NULL,
  "description" text,
  "colour" varchar(255) DEFAULT NULL,
  "read_only" smallint NOT NULL DEFAULT 0,
  "in_create" smallint NOT NULL DEFAULT 0,
  "menu_index" bigint DEFAULT NULL,
  "parent_node" varchar(255) DEFAULT NULL,
  "smallicon" varchar(255) DEFAULT NULL,
  "allow_copy" smallint NOT NULL DEFAULT 0,
  "allow_rename" smallint NOT NULL DEFAULT 0,
  "allow_import" smallint NOT NULL DEFAULT 0,
  "hide_toolbar" smallint NOT NULL DEFAULT 0,
  "track_seen" smallint NOT NULL DEFAULT 0,
  "max_attachments" bigint NOT NULL DEFAULT 0,
  "print_outline" varchar(255) DEFAULT NULL,
  "document_type" varchar(255) DEFAULT NULL,
  "icon" varchar(255) DEFAULT NULL,
  "color" varchar(255) DEFAULT NULL,
  "tag_fields" varchar(255) DEFAULT NULL,
  "subject" varchar(255) DEFAULT NULL,
  "_last_update" varchar(32) DEFAULT NULL,
  "engine" varchar(20) DEFAULT 'InnoDB',
  "default_print_format" varchar(255) DEFAULT NULL,
  "is_submittable" smallint NOT NULL DEFAULT 0,
  "show_name_in_global_search" smallint NOT NULL DEFAULT 0,
  "_user_tags" varchar(255) DEFAULT NULL,
  "custom" smallint NOT NULL DEFAULT 0,
  "beta" smallint NOT NULL DEFAULT 0,
  "has_web_view" smallint NOT NULL DEFAULT 0,
  "allow_guest_to_view" smallint NOT NULL DEFAULT 0,
  "route" varchar(255) DEFAULT NULL,
  "is_published_field" varchar(255) DEFAULT NULL,
  "website_search_field" varchar(255) DEFAULT NULL,
  "email_append_to" smallint NOT NULL DEFAULT 0,
  "subject_field" varchar(255) DEFAULT NULL,
  "sender_field" varchar(255) DEFAULT NULL,
  "show_title_field_in_link" smallint NOT NULL DEFAULT 0,
  "migration_hash" varchar(255) DEFAULT NULL,
  "translated_doctype" smallint NOT NULL DEFAULT 0,
  PRIMARY KEY ("name")
) ;

--
-- Table structure for table "tabSeries"
--

DROP TABLE IF EXISTS "tabSeries";
CREATE TABLE "tabSeries" (
  "name" varchar(100),
  "current" bigint NOT NULL DEFAULT 0,
  PRIMARY KEY ("name")
) ;

--
-- Table structure for table "tabSessions"
--

DROP TABLE IF EXISTS "tabSessions";
CREATE TABLE "tabSessions" (
  "user" varchar(255) DEFAULT NULL,
  "sid" varchar(255) DEFAULT NULL,
  "sessiondata" text,
  "ipaddress" varchar(16) DEFAULT NULL,
  "lastupdate" timestamp(6) DEFAULT NULL,
  "status" varchar(20) DEFAULT NULL
);

create index on "tabSessions" ("sid");

--
-- Table structure for table "tabSingles"
--

DROP TABLE IF EXISTS "tabSingles";
CREATE TABLE "tabSingles" (
  "doctype" varchar(255) DEFAULT NULL,
  "field" varchar(255) DEFAULT NULL,
  "value" text
);

create index on "tabSingles" ("doctype", "field");

--
-- Table structure for table "__Auth"
--

DROP TABLE IF EXISTS "__Auth";
CREATE TABLE "__Auth" (
	"doctype" VARCHAR(140) NOT NULL,
	"name" VARCHAR(255) NOT NULL,
	"fieldname" VARCHAR(140) NOT NULL,
	"password" TEXT NOT NULL,
	"encrypted" int NOT NULL DEFAULT 0,
	PRIMARY KEY ("doctype", "name", "fieldname")
);

create index on "__Auth" ("doctype", "name", "fieldname");

--
-- Table structure for table "tabFile"
--

DROP TABLE IF EXISTS "tabFile";
CREATE TABLE "tabFile" (
  "name" varchar(255) NOT NULL,
  "creation" timestamp(6) DEFAULT NULL,
  "modified" timestamp(6) DEFAULT NULL,
  "modified_by" varchar(255) DEFAULT NULL,
  "owner" varchar(255) DEFAULT NULL,
  "docstatus" smallint NOT NULL DEFAULT 0,
  "parent" varchar(255) DEFAULT NULL,
  "parentfield" varchar(255) DEFAULT NULL,
  "parenttype" varchar(255) DEFAULT NULL,
  "idx" bigint NOT NULL DEFAULT 0,
  "file_name" varchar(255) DEFAULT NULL,
  "file_url" varchar(255) DEFAULT NULL,
  "module" varchar(255) DEFAULT NULL,
  "attached_to_name" varchar(255) DEFAULT NULL,
  "file_size" bigint NOT NULL DEFAULT 0,
  "attached_to_doctype" varchar(255) DEFAULT NULL,
  PRIMARY KEY ("name")
);

create index on "tabFile" ("parent");
create index on "tabFile" ("attached_to_name");
create index on "tabFile" ("attached_to_doctype");

--
-- Table structure for table "tabDefaultValue"
--

DROP TABLE IF EXISTS "tabDefaultValue";
CREATE TABLE "tabDefaultValue" (
  "name" varchar(255) NOT NULL,
  "creation" timestamp(6) DEFAULT NULL,
  "modified" timestamp(6) DEFAULT NULL,
  "modified_by" varchar(255) DEFAULT NULL,
  "owner" varchar(255) DEFAULT NULL,
  "docstatus" smallint NOT NULL DEFAULT 0,
  "parent" varchar(255) DEFAULT NULL,
  "parentfield" varchar(255) DEFAULT NULL,
  "parenttype" varchar(255) DEFAULT NULL,
  "idx" bigint NOT NULL DEFAULT 0,
  "defvalue" text,
  "defkey" varchar(255) DEFAULT NULL,
  PRIMARY KEY ("name")
);

create index on "tabDefaultValue" ("parent");
create index on "tabDefaultValue" ("parent", "defkey");
