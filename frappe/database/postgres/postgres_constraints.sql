-- Postgres RLS constraints to be applied after creating the site

-- At time of site creation we sometimes do schema changes for internal tables.
-- let's force RLS for the DB creator after site is created.

ALTER TABLE "tabSeries" FORCE ROW LEVEL SECURITY;
ALTER TABLE "tabSessions" FORCE ROW LEVEL SECURITY;
ALTER TABLE "tabSingles" FORCE ROW LEVEL SECURITY;
ALTER TABLE "tabFile" FORCE ROW LEVEL SECURITY;
ALTER TABLE "__Auth" FORCE ROW LEVEL SECURITY;
