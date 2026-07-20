-- ============================================================
-- Cazal Réfrigération — Base de données contenu (Supabase)
-- À exécuter UNE FOIS dans le SQL Editor de Supabase, quand le
-- compte/projet de Loïc existera (cf. MIGRATION-SUPABASE.md).
-- Calqué sur Master-content/lessons/1.5-build-database/resources/setup-database.sql
-- avec, en plus, une table `comptes` normalisée.
-- Noms de tables en français ; colonnes alignées sur Master-content.
-- ============================================================

-- 1. COMPTES — d'où sont postés les contenus (reel IG, reel/post Facebook…)
CREATE TABLE comptes (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  handle text NOT NULL,
  plateforme text NOT NULL DEFAULT 'instagram',   -- instagram | facebook
  type text NOT NULL DEFAULT 'own',               -- own | concurrent
  nom text,
  url text,
  note text,
  created_at timestamp DEFAULT now(),
  CONSTRAINT comptes_unique UNIQUE (handle, plateforme)
);

-- 2. CONTENU — chaque contenu + KPIs + analyse IA, lié au compte qui l'a posté
CREATE TABLE contenu (
  id text PRIMARY KEY,                              -- id média de la plateforme
  compte_id uuid REFERENCES comptes(id),
  plateforme text NOT NULL DEFAULT 'instagram',
  url text,
  thumbnail_url text,
  caption text,
  duration numeric,
  post_date timestamp,
  -- KPIs
  views integer DEFAULT 0,
  reach integer DEFAULT 0,
  likes integer DEFAULT 0,
  comments integer DEFAULT 0,
  shares integer DEFAULT 0,
  saves integer DEFAULT 0,
  plays integer DEFAULT 0,
  replays integer DEFAULT 0,
  total_watch_time integer DEFAULT 0,
  avg_watch_time numeric DEFAULT 0,
  total_interactions integer DEFAULT 0,
  -- Analyse IA
  transcript text,
  spoken_hook text,
  hook_framework text,
  hook_structure text,
  text_hook text,
  visual_hook text,
  visual_format text,
  audio_hook text,
  topic text,
  topic_summary text,
  content_structure text,
  content_type text,
  call_to_action text,
  -- Méta
  is_analyzed boolean DEFAULT false,
  analyzed_at timestamp,
  -- embedding vector,                             -- DIFFÉRÉ (pgvector) : décommenter après
  --                                                  CREATE EXTENSION IF NOT EXISTS vector;
  metrics_updated_at timestamp,
  created_at timestamp DEFAULT now()
);

-- 3. CONTENU_SNAPSHOTS — une ligne par contenu par jour (alimentée par le Poller)
CREATE TABLE contenu_snapshots (
  id text PRIMARY KEY,                              -- <contenu_id>_<YYYY-MM-DD>
  contenu_id text REFERENCES contenu(id),
  snapshot_date date NOT NULL,
  views integer DEFAULT 0,
  reach integer DEFAULT 0,
  likes integer DEFAULT 0,
  comments integer DEFAULT 0,
  shares integer DEFAULT 0,
  saves integer DEFAULT 0,
  avg_watch_time numeric DEFAULT 0,
  total_watch_time integer DEFAULT 0,
  created_at timestamp DEFAULT now()
);

-- 4. COMPTE_STATS — métriques agrégées par compte et par jour (auto via trigger)
CREATE TABLE compte_stats (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  compte_id uuid REFERENCES comptes(id),
  plateforme text NOT NULL DEFAULT 'instagram',
  snapshot_date date NOT NULL,
  follower_count integer DEFAULT 0,
  post_count integer DEFAULT 0,
  avg_views numeric DEFAULT 0,
  total_views integer DEFAULT 0,
  created_at timestamp DEFAULT now(),
  CONSTRAINT compte_stats_unique UNIQUE (compte_id, snapshot_date)
);

-- 5. IDEES — pipeline d'idées (équivalent de l'Airtable Pipeline de Master-content)
CREATE TABLE idees (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sujet text NOT NULL,
  archetype text,
  angle text,
  cadrage text,
  format text,                                     -- reel | article | both
  statut text NOT NULL DEFAULT 'idée',             -- idée | choisie | produite | publiée
  pourquoi text,
  origine text DEFAULT 'veille',                   -- veille | chantier | manuelle
  compte_id uuid REFERENCES comptes(id),
  notes text,
  source_url text,                                 -- URL réelle de la source (ou lien recherche Google si pas d'URL de page)
  created_at timestamp DEFAULT now()
);

-- Index utiles
CREATE INDEX idx_contenu_compte ON contenu(compte_id);
CREATE INDEX idx_contenu_url ON contenu(url);
CREATE INDEX idx_snapshots_contenu ON contenu_snapshots(contenu_id);
CREATE INDEX idx_idees_statut ON idees(statut);

-- 6. VUE — calcule outlier score + catégorie + engagement (comme content_with_scores)
CREATE VIEW contenu_avec_scores AS
SELECT
  c.*,
  CASE WHEN a.avg_views > 0 THEN ROUND((c.views::numeric / a.avg_views), 2) ELSE 0 END
    AS calc_outlier_score,
  CASE
    WHEN a.avg_views > 0 AND (c.views::numeric / a.avg_views) >= 5   THEN 'viral'
    WHEN a.avg_views > 0 AND (c.views::numeric / a.avg_views) >= 2   THEN 'hit'
    WHEN a.avg_views > 0 AND (c.views::numeric / a.avg_views) >= 1.5 THEN 'above_average'
    WHEN a.avg_views > 0 AND (c.views::numeric / a.avg_views) >= 0.5 THEN 'average'
    ELSE 'below_average'
  END AS calc_outlier_category,
  CASE WHEN c.views > 0
    THEN ROUND(((c.likes + c.comments + c.shares + c.saves)::numeric / c.views * 100), 2)
    ELSE 0 END AS calc_engagement_rate
FROM contenu c
LEFT JOIN (
  SELECT compte_id, avg_views
  FROM compte_stats
  WHERE (compte_id, snapshot_date) IN (
    SELECT compte_id, MAX(snapshot_date) FROM compte_stats GROUP BY compte_id
  )
) a ON c.compte_id = a.compte_id;

-- 7. TRIGGER — recalcule compte_stats à chaque upsert de contenu
CREATE OR REPLACE FUNCTION update_compte_stats()
RETURNS TRIGGER AS $$
DECLARE
  v_avg numeric;
  v_total bigint;
  v_count integer;
  v_today date := CURRENT_DATE;
  v_plateforme text;
BEGIN
  IF NEW.compte_id IS NULL THEN
    RETURN NEW;
  END IF;

  SELECT AVG(views), SUM(views), COUNT(*)
  INTO v_avg, v_total, v_count
  FROM contenu WHERE compte_id = NEW.compte_id;

  SELECT plateforme INTO v_plateforme FROM comptes WHERE id = NEW.compte_id;

  INSERT INTO compte_stats (compte_id, plateforme, snapshot_date, avg_views, total_views, post_count)
  VALUES (NEW.compte_id, COALESCE(v_plateforme, 'instagram'), v_today, v_avg, v_total, v_count)
  ON CONFLICT ON CONSTRAINT compte_stats_unique
  DO UPDATE SET avg_views = v_avg, total_views = v_total, post_count = v_count;

  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_update_compte_stats
AFTER INSERT OR UPDATE ON contenu
FOR EACH ROW EXECUTE FUNCTION update_compte_stats();

-- 8. RLS — accès via la clé (comme Master-content)
ALTER TABLE comptes ENABLE ROW LEVEL SECURITY;
ALTER TABLE contenu ENABLE ROW LEVEL SECURITY;
ALTER TABLE contenu_snapshots ENABLE ROW LEVEL SECURITY;
ALTER TABLE compte_stats ENABLE ROW LEVEL SECURITY;
ALTER TABLE idees ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Allow all for anon" ON comptes            FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON contenu            FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON contenu_snapshots  FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON compte_stats       FOR ALL USING (true) WITH CHECK (true);
CREATE POLICY "Allow all for anon" ON idees              FOR ALL USING (true) WITH CHECK (true);

-- 9. SYNTHESES — digests & rapports de perf datés, lus en live par les skills (connecteur MCP).
-- type 'digest-perf' = LE digest que les skills de rédaction lisent (dernier par run_date) ;
-- types 'rapport-performance' / 'rapport-concurrents' = rapports complets datés (archives).
CREATE TABLE IF NOT EXISTS syntheses (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  type text NOT NULL,
  titre text,
  contenu text NOT NULL,                            -- markdown complet
  run_date date NOT NULL,
  source text,                                      -- skill producteur
  created_at timestamp DEFAULT now(),
  CONSTRAINT syntheses_unique UNIQUE (type, run_date)
);
CREATE INDEX IF NOT EXISTS idx_syntheses_type_date ON syntheses(type, run_date DESC);
ALTER TABLE syntheses ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow all for anon" ON syntheses FOR ALL USING (true) WITH CHECK (true);

-- NOTE pgvector (différé) : pour activer la colonne `embedding`, exécuter d'abord
--   CREATE EXTENSION IF NOT EXISTS vector;
-- puis (re)créer la colonne en vector(1536) si on passe aux embeddings OpenAI.
