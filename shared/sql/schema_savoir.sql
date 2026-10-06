-- =====================================================================================================
-- Base de savoir « froid » — schéma (idempotent, rejouable). Projet Supabase de Loïc, schéma public.
-- Convention : tables préfixées savoir_ dans public (comme le reste de la base), RLS « Allow all for anon »
-- (même convention que schema.sql : base privée, clé anon uniquement dans le .env du PC).
-- Une page = une ligne savoir_pages = un chunk savoir_chunks (table séparée pour pouvoir découper plus tard).
-- Recherche : plein texte français sans accents (config french_unaccent) + vecteurs (text-embedding-3-small).
-- Appliqué le 2026-10-03 (POC) ; fonction rechercher_savoir en v2 (tous les mots d'abord, repli « au moins un mot »).
-- Pour rejouer : python shared/scripts/sql/appliquer_sql.py shared/sql/schema_savoir.sql
-- =====================================================================================================

create extension if not exists vector with schema extensions;
create extension if not exists unaccent with schema extensions;

do $$
begin
  if not exists (select 1 from pg_ts_config where cfgname = 'french_unaccent') then
    create text search configuration public.french_unaccent (copy = pg_catalog.french);
    alter text search configuration public.french_unaccent
      alter mapping for hword, hword_part, word with extensions.unaccent, french_stem;
  end if;
end $$;

create table if not exists savoir_documents (
  id             text primary key,
  titre          text not null,
  type           text,                             -- livre | formation | notice | fiche-fournisseur | abaque | guide | autre
  marque         text,
  langue         text default 'fr',
  nature         text check (nature in ('scan', 'natif')),
  pages_total    int,
  decalage_page  int default 0,                    -- page imprimée = page PDF - decalage_page (repli si le numéro n'est pas lu)
  fichier_source text,                             -- chemin relatif à dimensionnement/bibliotheque/ sur le PC
  ocr_modele     text,
  ingere_le      timestamptz default now(),
  notes          text
);

create table if not exists savoir_sections (
  id          bigserial primary key,
  document_id text not null references savoir_documents(id) on delete cascade,
  titre       text not null,
  niveau      int default 1,
  page_debut  int,
  page_fin    int,
  parent_id   bigint references savoir_sections(id) on delete set null
);
create index if not exists savoir_sections_doc on savoir_sections (document_id, page_debut);
create index if not exists savoir_sections_parent on savoir_sections (parent_id);   -- clé étrangère : indispensable aux suppressions

create table if not exists savoir_pages (
  id                   bigserial primary key,
  document_id          text not null references savoir_documents(id) on delete cascade,
  page_pdf             int not null,
  page_imprimee        int,
  page_lue             int,
  section_id           bigint references savoir_sections(id) on delete set null,
  chapitre             text,
  type                 text,                       -- texte | exercice | corrige | quiz | tableau | figure | sommaire | mixte
  texte                text not null default '',
  descriptions_figures text not null default '',
  confiance            real,
  image_path           text,
  image_url            text,
  image_url_expire     timestamptz,
  unique (document_id, page_pdf)
);

create table if not exists savoir_chunks (
  id            bigserial primary key,
  page_id       bigint not null references savoir_pages(id) on delete cascade,
  document_id   text not null,
  page_imprimee int,
  titre_section text not null default '',
  contenu       text not null,
  fts           tsvector generated always as (
                  setweight(to_tsvector('public.french_unaccent'::regconfig, titre_section), 'A') ||
                  setweight(to_tsvector('public.french_unaccent'::regconfig, contenu), 'B')
                ) stored,
  embedding     extensions.vector(1536)
);
create index if not exists savoir_chunks_fts on savoir_chunks using gin (fts);
create index if not exists savoir_chunks_page on savoir_chunks (page_id);
create index if not exists savoir_pages_section on savoir_pages (section_id);   -- clé étrangère (on delete set null) : indispensable aux suppressions
create index if not exists savoir_chunks_embedding on savoir_chunks using hnsw (embedding extensions.vector_cosine_ops);

create table if not exists savoir_figures (
  id            text primary key,                  -- '<doc>-<page_pdf>-<k>'
  page_id       bigint not null references savoir_pages(id) on delete cascade,
  document_id   text not null,
  page_imprimee int,
  bbox          jsonb,
  type          text,
  description   text,
  reperes       jsonb,
  mots_cles     text[],
  image_path    text,
  image_url     text
);
create index if not exists savoir_figures_page on savoir_figures (page_id);

create table if not exists savoir_renvois (
  id              bigserial primary key,
  page_id         bigint not null references savoir_pages(id) on delete cascade,
  page_cible      int not null,
  page_cible_fin  int
);

do $$
declare t text;
begin
  foreach t in array array['savoir_documents','savoir_sections','savoir_pages','savoir_chunks','savoir_figures','savoir_renvois'] loop
    execute format('alter table public.%I enable row level security', t);
    if not exists (select 1 from pg_policies where schemaname = 'public' and tablename = t and policyname = 'Allow all for anon') then
      execute format('create policy "Allow all for anon" on public.%I for all using (true) with check (true)', t);
    end if;
  end loop;
end $$;

-- Recherche plein texte v2 : « tous les mots » d'abord, repli « au moins un mot » ; pages de sommaire exclues.
drop function if exists rechercher_savoir(text, integer, text);
create or replace function rechercher_savoir(q text, limite int default 5, doc text default null)
returns table (
  document_id    text,
  titre_document text,
  page_imprimee  int,
  titre_section  text,
  extrait        text,
  rang           real,
  mode           text,
  figures        jsonb,
  image_url      text,
  renvois        int[]
)
language sql stable security invoker
as $$
  with req as (
    select websearch_to_tsquery('public.french_unaccent'::regconfig, q) as tq_and,
           websearch_to_tsquery('public.french_unaccent'::regconfig,
                                regexp_replace(regexp_replace(q, '[[:punct:]]+', ' ', 'g'), '\s+', ' or ', 'g')) as tq_or
  ),
  hits as (
    select c.id, c.page_id, c.document_id, c.page_imprimee, c.titre_section, c.contenu,
           (c.fts @@ req.tq_and) as tous_les_mots,
           case when c.fts @@ req.tq_and then ts_rank_cd(c.fts, req.tq_and) + 1.0 else ts_rank_cd(c.fts, req.tq_or) end as score,
           req.tq_or as tq
    from savoir_chunks c
    join req on true
    join savoir_pages p on p.id = c.page_id
    where c.fts @@ req.tq_or
      and coalesce(p.type, '') <> 'sommaire'
      and (doc is null or c.document_id = doc)
  )
  select h.document_id,
         d.titre,
         h.page_imprimee,
         h.titre_section,
         ts_headline('public.french_unaccent'::regconfig, h.contenu, h.tq,
                     'MaxFragments=2, MaxWords=45, MinWords=15, FragmentDelimiter= … ') as extrait,
         h.score::real as rang,
         case when h.tous_les_mots then 'tous les mots' else 'au moins un mot' end as mode,
         (select coalesce(jsonb_agg(jsonb_build_object('id', f.id, 'type', f.type, 'description', f.description, 'image_url', f.image_url)), '[]'::jsonb)
            from savoir_figures f where f.page_id = h.page_id) as figures,
         p.image_url,
         (select coalesce(array_agg(r.page_cible order by r.page_cible), '{}') from savoir_renvois r where r.page_id = h.page_id) as renvois
  from hits h
  join savoir_pages p on p.id = h.page_id
  join savoir_documents d on d.id = h.document_id
  order by h.tous_les_mots desc, h.score desc, h.page_imprimee
  limit limite;
$$;

create or replace function rechercher_savoir_vec(q_embedding extensions.vector(1536), limite int default 5, doc text default null)
returns table (
  document_id   text,
  titre_document text,
  page_imprimee int,
  titre_section text,
  extrait       text,
  similarite    real,
  image_url     text
)
language sql stable security invoker
as $$
  select c.document_id, d.titre, c.page_imprimee, c.titre_section,
         left(c.contenu, 400) as extrait,
         (1 - (c.embedding <=> q_embedding))::real as similarite,
         p.image_url
  from savoir_chunks c
  join savoir_pages p on p.id = c.page_id
  join savoir_documents d on d.id = c.document_id
  where c.embedding is not null
    and (doc is null or c.document_id = doc)
  order by c.embedding <=> q_embedding
  limit limite;
$$;

insert into storage.buckets (id, name, public)
values ('savoir-pages', 'savoir-pages', false)
on conflict (id) do nothing;

do $$
begin
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'savoir-pages anon select') then
    create policy "savoir-pages anon select" on storage.objects for select to anon using (bucket_id = 'savoir-pages');
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'savoir-pages anon insert') then
    create policy "savoir-pages anon insert" on storage.objects for insert to anon with check (bucket_id = 'savoir-pages');
  end if;
  if not exists (select 1 from pg_policies where schemaname = 'storage' and tablename = 'objects' and policyname = 'savoir-pages anon update') then
    create policy "savoir-pages anon update" on storage.objects for update to anon using (bucket_id = 'savoir-pages') with check (bucket_id = 'savoir-pages');
  end if;
end $$;

select 'tables' as quoi, string_agg(tablename, ', ' order by tablename) as detail
  from pg_tables where schemaname = 'public' and tablename like 'savoir_%'
union all
select 'fonctions', string_agg(proname, ', ') from pg_proc where proname like 'rechercher_savoir%'
union all
select 'bucket', coalesce(string_agg(id, ', '), '(aucun)') from storage.buckets where id = 'savoir-pages';
