-- Oracle SQL script for creating table "tabDocField"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabDocField" PURGE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabDocField" (
  "name" VARCHAR2(255) NOT NULL,
  "creation" TIMESTAMP(6),
  "modified" TIMESTAMP(6),
  "modified_by" VARCHAR2(255),
  "owner" VARCHAR2(255),
  "docstatus" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "parent" VARCHAR2(255),
  "parentfield" VARCHAR2(255),
  "parenttype" VARCHAR2(255),
  "idx" NUMBER DEFAULT 0 NOT NULL,
  "fieldname" VARCHAR2(255),
  "label" VARCHAR2(255),
  "oldfieldname" VARCHAR2(255),
  "fieldtype" VARCHAR2(255),
  "oldfieldtype" VARCHAR2(255),
  "options" VARCHAR(4000),
  "search_index" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "show_dashboard" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "hidden" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "set_only_once" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "allow_in_quick_entry" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "print_hide" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "report_hide" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "reqd" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "bold" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "in_global_search" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "collapsible" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "unique" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "no_copy" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "allow_on_submit" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "show_preview_popup" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "trigger" VARCHAR2(255),
  "collapsible_depends_on" VARCHAR(4000),
  "mandatory_depends_on" VARCHAR(4000),
  "read_only_depends_on" VARCHAR(4000),
  "depends_on" VARCHAR(4000),
  "permlevel" NUMBER DEFAULT 0 NOT NULL,
  "ignore_user_permissions" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "width" VARCHAR2(255),
  "print_width" VARCHAR2(255),
  "columns" NUMBER DEFAULT 0 NOT NULL,
  "default" VARCHAR(4000),
  "description" VARCHAR(4000),
  "in_list_view" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "fetch_if_empty" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "in_filter" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "remember_last_selected_value" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "ignore_xss_filter" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "print_hide_if_no_value" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "allow_bulk_edit" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "in_standard_filter" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "in_preview" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "read_only" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "precision" VARCHAR2(255),
  "max_height" VARCHAR2(10),
  "length" NUMBER DEFAULT 0 NOT NULL,
  "translatable" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "hide_border" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "hide_days" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "hide_seconds" NUMBER(3,0) DEFAULT 0 NOT NULL,
  CONSTRAINT "pk_tabDocField" PRIMARY KEY ("name")
);

CREATE INDEX "idx_parent_tabDocField" ON "tabDocField" ("parent");
CREATE INDEX "idx_label_tabDocField" ON "tabDocField" ("label");
CREATE INDEX "idx_fieldtype_tabDocField" ON "tabDocField" ("fieldtype");
CREATE INDEX "idx_fieldname_tabDocField" ON "tabDocField" ("fieldname");

-- Table structure for table "tabDocPerm"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabDocPerm" PURGE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabDocPerm" (
  "name" VARCHAR2(255) NOT NULL,
  "creation" TIMESTAMP(6),
  "modified" TIMESTAMP(6),
  "modified_by" VARCHAR2(255),
  "owner" VARCHAR2(255),
  "docstatus" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "parent" VARCHAR2(255),
  "parentfield" VARCHAR2(255),
  "parenttype" VARCHAR2(255),
  "idx" NUMBER DEFAULT 0 NOT NULL,
  "permlevel" NUMBER DEFAULT 0,
  "role" VARCHAR2(255),
  "match" VARCHAR2(255),
  "read" NUMBER(3,0) DEFAULT 1 NOT NULL,
  "write" NUMBER(3,0) DEFAULT 1 NOT NULL,
  "create" NUMBER(3,0) DEFAULT 1 NOT NULL,
  "submit" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "cancel" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "delete" NUMBER(3,0) DEFAULT 1 NOT NULL,
  "amend" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "report" NUMBER(3,0) DEFAULT 1 NOT NULL,
  "export" NUMBER(3,0) DEFAULT 1 NOT NULL,
  "import" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "share" NUMBER(3,0) DEFAULT 1 NOT NULL,
  "print" NUMBER(3,0) DEFAULT 1 NOT NULL,
  "email" NUMBER(3,0) DEFAULT 1 NOT NULL,
  CONSTRAINT "pk_tabDocPerm" PRIMARY KEY ("name")
);

CREATE INDEX "idx_parent_tabDocPerm" ON "tabDocPerm" ("parent");

-- Table structure for table "tabDocType Action"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabDocType Action" CASCADE CONSTRAINTS';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabDocType Action" (
  "name" VARCHAR2(140) NOT NULL,
  "creation" TIMESTAMP(6) DEFAULT NULL,
  "modified" TIMESTAMP(6) DEFAULT NULL,
  "modified_by" VARCHAR2(140) DEFAULT NULL,
  "owner" VARCHAR2(140) DEFAULT NULL,
  "docstatus" NUMBER(1) DEFAULT 0 NOT NULL,
  "parent" VARCHAR2(140) DEFAULT NULL,
  "parentfield" VARCHAR2(140) DEFAULT NULL,
  "parenttype" VARCHAR2(140) DEFAULT NULL,
  "idx" NUMBER DEFAULT 0 NOT NULL,
  "label" VARCHAR2(140) DEFAULT NULL,
  "group" VARCHAR2(140) DEFAULT NULL,
  "action_type" VARCHAR2(140) DEFAULT NULL,
  "action" VARCHAR(4000) DEFAULT NULL,
  PRIMARY KEY ("name")
);

CREATE INDEX "IDX_TABDOC_ACTION_PARENT" ON "tabDocType Action" ("parent");

-- Table structure for table "tabDocType Link"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabDocType Link" CASCADE CONSTRAINTS';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabDocType Link" (
  "name" VARCHAR2(140) NOT NULL,
  "creation" TIMESTAMP(6) DEFAULT NULL,
  "modified" TIMESTAMP(6) DEFAULT NULL,
  "modified_by" VARCHAR2(140) DEFAULT NULL,
  "owner" VARCHAR2(140) DEFAULT NULL,
  "docstatus" NUMBER(1) DEFAULT 0 NOT NULL,
  "parent" VARCHAR2(140) DEFAULT NULL,
  "parentfield" VARCHAR2(140) DEFAULT NULL,
  "parenttype" VARCHAR2(140) DEFAULT NULL,
  "idx" NUMBER DEFAULT 0 NOT NULL,
  "group" VARCHAR2(140) DEFAULT NULL,
  "link_doctype" VARCHAR2(140) DEFAULT NULL,
  "link_fieldname" VARCHAR2(140) DEFAULT NULL,
  PRIMARY KEY ("name")
);

CREATE INDEX "IDX_TABDOC_LINK_PARENT" ON "tabDocType Link" ("parent");

-- Table structure for table "tabDocType"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabDocType" CASCADE CONSTRAINTS';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabDocType" (
  "name" VARCHAR2(255) NOT NULL,
  "creation" TIMESTAMP(6) DEFAULT NULL,
  "modified" TIMESTAMP(6) DEFAULT NULL,
  "modified_by" VARCHAR2(255) DEFAULT NULL,
  "owner" VARCHAR2(255) DEFAULT NULL,
  "docstatus" NUMBER(1) DEFAULT 0 NOT NULL,
  "idx" NUMBER DEFAULT 0 NOT NULL,
  "search_fields" VARCHAR2(255) DEFAULT NULL,
  "issingle" NUMBER(1) DEFAULT 0 NOT NULL,
  "is_virtual" NUMBER(1) DEFAULT 0 NOT NULL,
  "is_tree" NUMBER(1) DEFAULT 0 NOT NULL,
  "istable" NUMBER(1) DEFAULT 0 NOT NULL,
  "editable_grid" NUMBER(1) DEFAULT 1 NOT NULL,
  "track_changes" NUMBER(1) DEFAULT 0 NOT NULL,
  "module" VARCHAR2(255) DEFAULT NULL,
  "restrict_to_domain" VARCHAR2(255) DEFAULT NULL,
  "app" VARCHAR2(255) DEFAULT NULL,
  "autoname" VARCHAR2(255) DEFAULT NULL,
  "naming_rule" VARCHAR2(40) DEFAULT NULL,
  "title_field" VARCHAR2(255) DEFAULT NULL,
  "image_field" VARCHAR2(255) DEFAULT NULL,
  "timeline_field" VARCHAR2(255) DEFAULT NULL,
  "sort_field" VARCHAR2(255) DEFAULT NULL,
  "sort_order" VARCHAR2(255) DEFAULT NULL,
  "description" VARCHAR(4000) DEFAULT NULL,
  "colour" VARCHAR2(255) DEFAULT NULL,
  "read_only" NUMBER(1) DEFAULT 0 NOT NULL,
  "in_create" NUMBER(1) DEFAULT 0 NOT NULL,
  "menu_index" NUMBER DEFAULT NULL,
  "parent_node" VARCHAR2(255) DEFAULT NULL,
  "smallicon" VARCHAR2(255) DEFAULT NULL,
  "allow_copy" NUMBER(1) DEFAULT 0 NOT NULL,
  "allow_rename" NUMBER(1) DEFAULT 0 NOT NULL,
  "allow_import" NUMBER(1) DEFAULT 0 NOT NULL,
  "hide_toolbar" NUMBER(1) DEFAULT 0 NOT NULL,
  "track_seen" NUMBER(1) DEFAULT 0 NOT NULL,
  "max_attachments" NUMBER DEFAULT 0 NOT NULL,
  "print_outline" VARCHAR2(255) DEFAULT NULL,
  "document_type" VARCHAR2(255) DEFAULT NULL,
  "icon" VARCHAR2(255) DEFAULT NULL,
  "color" VARCHAR2(255) DEFAULT NULL,
  "tag_fields" VARCHAR2(255) DEFAULT NULL,
  "subject" VARCHAR2(255) DEFAULT NULL,
  "_last_update" VARCHAR2(32) DEFAULT NULL,
  "engine" VARCHAR2(20) DEFAULT 'InnoDB',
  "default_print_format" VARCHAR2(255) DEFAULT NULL,
  "is_submittable" NUMBER(1) DEFAULT 0 NOT NULL,
  "show_name_in_global_search" NUMBER(1) DEFAULT 0 NOT NULL,
  "_user_tags" VARCHAR2(255) DEFAULT NULL,
  "custom" NUMBER(1) DEFAULT 0 NOT NULL,
  "beta" NUMBER(1) DEFAULT 0 NOT NULL,
  "has_web_view" NUMBER(1) DEFAULT 0 NOT NULL,
  "allow_guest_to_view" NUMBER(1) DEFAULT 0 NOT NULL,
  "route" VARCHAR2(255) DEFAULT NULL,
  "is_published_field" VARCHAR2(255) DEFAULT NULL,
  "website_search_field" VARCHAR2(255) DEFAULT NULL,
  "email_append_to" NUMBER(1) DEFAULT 0 NOT NULL,
  "subject_field" VARCHAR2(255) DEFAULT NULL,
  "sender_field" VARCHAR2(255) DEFAULT NULL,
  "show_title_field_in_link" NUMBER(1) DEFAULT 0 NOT NULL,
  "migration_hash" VARCHAR2(255) DEFAULT NULL,
  "translated_doctype" NUMBER(1) DEFAULT 0 NOT NULL,
  PRIMARY KEY ("name")
);

-- Table structure for table "tabSeries"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabSeries" PURGE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabSeries" (
  "name" VARCHAR2(100) NOT NULL,
  "current" NUMBER DEFAULT 0 NOT NULL,
  CONSTRAINT "pk_tabSeries" PRIMARY KEY ("name")
);

-- Table structure for table "tabSessions"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabSessions" PURGE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabSessions" (
  "user" VARCHAR2(255),
  "sid" VARCHAR2(255),
  "sessiondata" VARCHAR(4000),
  "ipaddress" VARCHAR2(16),
  "lastupdate" TIMESTAMP(6),
  "status" VARCHAR2(20),
  CONSTRAINT "idx_sid_tabSessions" UNIQUE ("sid")
);

-- Table structure for table "tabSingles"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabSingles" PURGE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabSingles" (
  "doctype" VARCHAR2(255),
  "field" VARCHAR2(255),
  "value" VARCHAR(4000),
  CONSTRAINT "singles_doctype_field_index" UNIQUE ("doctype", "field")
);

-- Table structure for table "__Auth"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "__Auth" PURGE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "__Auth" (
  "doctype" VARCHAR2(140) NOT NULL,
  "name" VARCHAR2(255) NOT NULL,
  "fieldname" VARCHAR2(140) NOT NULL,
  "password" VARCHAR(4000) NOT NULL,
  "encrypted" NUMBER(3,0) DEFAULT 0 NOT NULL,
  CONSTRAINT "pk___Auth" PRIMARY KEY ("doctype", "name", "fieldname")
);

-- Table structure for table "tabFile"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabFile" PURGE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabFile" (
  "name" VARCHAR2(255) NOT NULL,
  "creation" TIMESTAMP(6),
  "modified" TIMESTAMP(6),
  "modified_by" VARCHAR2(255),
  "owner" VARCHAR2(255),
  "docstatus" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "parent" VARCHAR2(255),
  "parentfield" VARCHAR2(255),
  "parenttype" VARCHAR2(255),
  "idx" NUMBER DEFAULT 0 NOT NULL,
  "file_name" VARCHAR2(255),
  "file_url" VARCHAR2(255),
  "module" VARCHAR2(255),
  "attached_to_name" VARCHAR2(255),
  "file_size" NUMBER DEFAULT 0 NOT NULL,
  "attached_to_doctype" VARCHAR2(255),
  CONSTRAINT "pk_tabFile" PRIMARY KEY ("name")
);

CREATE INDEX "idx_parent_tabFile" ON "tabFile" ("parent");
CREATE INDEX "idx_creation_tabFile" ON "tabFile" ("creation");
CREATE INDEX "idx_attached_to_name_tabFile" ON "tabFile" ("attached_to_name");
CREATE INDEX "idx_attached_to_doctype_tabFile" ON "tabFile" ("attached_to_doctype");

-- Table structure for table "tabDefaultValue"
BEGIN
   EXECUTE IMMEDIATE 'DROP TABLE "tabDefaultValue" PURGE';
EXCEPTION
   WHEN OTHERS THEN
      IF SQLCODE != -942 THEN
         RAISE;
      END IF;
END;
/

CREATE TABLE "tabDefaultValue" (
  "name" VARCHAR2(255) NOT NULL,
  "creation" TIMESTAMP(6),
  "modified" TIMESTAMP(6),
  "modified_by" VARCHAR2(255),
  "owner" VARCHAR2(255),
  "docstatus" NUMBER(3,0) DEFAULT 0 NOT NULL,
  "parent" VARCHAR2(255),
  "parentfield" VARCHAR2(255),
  "parenttype" VARCHAR2(255),
  "idx" NUMBER DEFAULT 0 NOT NULL,
  "defvalue" VARCHAR(4000),
  "defkey" VARCHAR2(255),
  CONSTRAINT "pk_tabDefaultValue" PRIMARY KEY ("name")
);

CREATE UNIQUE INDEX "defaultvalue_parent_defkey_index" ON "tabDefaultValue" ("parent", "defkey");

EXIT;

