-- Preserve SEC source text before typed conversion; each row keeps filing-batch provenance.
CREATE SCHEMA IF NOT EXISTS staging;
CREATE TABLE staging.sec_sub (
    source_quarter text NOT NULL, adsh text, cik text, name text, sic text,
    countryba text, stprba text, cityba text, zipba text, bas1 text, bas2 text,
    baph text, countryma text, stprma text, cityma text, zipma text, mas1 text,
    mas2 text, countryinc text, stprinc text, ein text, former text, changed text,
    afs text, wksi text, fye text, form text, period text, fy text, fp text,
    filed text, accepted text, prevrpt text, detail text, instance text, nciks text, aciks text
);
CREATE TABLE staging.sec_num (
    source_quarter text NOT NULL, adsh text, tag text, version text, ddate text,
    qtrs text, uom text, segments text, coreg text, value text, footnote text
);
CREATE TABLE staging.sec_tag (
    source_quarter text NOT NULL, tag text, version text, custom text, abstract text,
    datatype text, iord text, crdr text, tlabel text, doc text
);
CREATE TABLE staging.sec_pre (
    source_quarter text NOT NULL, adsh text, report text, line text, stmt text,
    inpth text, rfile text, tag text, version text, plabel text, negating text
);
