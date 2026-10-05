"""Applique un fichier SQL dans le projet Supabase via l'API de gestion (token personnel du compte propriétaire).

Doc (lue le 2026-10-03) : POST https://api.supabase.com/v1/projects/{ref}/database/query,
Bearer <personal access token>, body {"query": "...", "read_only": false} → 201 + JSON.
Token : CIBLE_SUPABASE_ACCESS_TOKEN s'il est posé (build chez Adrien), sinon SUPABASE_ACCESS_TOKEN (PC de Loïc).

Usage : python shared/scripts/sql/appliquer_sql.py shared/sql/schema_savoir.sql     (applique)
        python shared/scripts/sql/appliquer_sql.py --check                          (tables savoir_*, fonctions, bucket, taille du stockage)
Alternative sans token : coller le .sql dans Dashboard ▸ SQL Editor du projet.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from shared.savoir import project_ref, sortie_utf8  # noqa: E402

API = "https://api.supabase.com/v1"


def token() -> str:
    for k in ("CIBLE_SUPABASE_ACCESS_TOKEN", "SUPABASE_ACCESS_TOKEN"):
        v = os.environ.get(k, "").strip()
        if v and not v.startswith("REPLACE"):
            return v
    raise SystemExit("Aucun token de gestion Supabase dans .env (SUPABASE_ACCESS_TOKEN ou CIBLE_SUPABASE_ACCESS_TOKEN)")


def appel(method: str, url: str, body: dict | None = None):
    req = urllib.request.Request(url, method=method, headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
                                 data=json.dumps(body).encode() if body is not None else None)
    try:
        with urllib.request.urlopen(req, timeout=120) as r:
            return r.status, json.loads(r.read().decode() or "null")
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode()[:400]


def run_sql(sql: str, read_only: bool = False):
    code, data = appel("POST", f"{API}/projects/{project_ref()}/database/query", {"query": sql, "read_only": read_only})
    if code not in (200, 201):
        raise SystemExit(f"HTTP {code} : {data}")
    return data


CHECK = """
select 'tables' as quoi, coalesce(string_agg(tablename, ', ' order by tablename), '(aucune)') as detail
  from pg_tables where schemaname = 'public' and tablename like 'savoir_%'
union all select 'fonctions', coalesce(string_agg(proname, ', '), '(aucune)') from pg_proc where proname like 'rechercher_savoir%'
union all select 'bucket', coalesce(string_agg(id, ', '), '(aucun)') from storage.buckets where id = 'savoir-pages'
union all select 'documents', (select count(*)::text from savoir_documents)
union all select 'pages', (select count(*)::text from savoir_pages)
union all select 'chunks vectorisés', (select count(*)::text from savoir_chunks where embedding is not null)
union all select 'stockage savoir-pages (Mo)',
  (select coalesce(round(sum((metadata->>'size')::numeric) / 1048576, 1), 0)::text from storage.objects where bucket_id = 'savoir-pages')
union all select 'stockage tous buckets (Mo)',
  (select coalesce(round(sum((metadata->>'size')::numeric) / 1048576, 1), 0)::text from storage.objects);
"""


def main() -> None:
    sortie_utf8()
    if "--check" in sys.argv:
        for row in run_sql(CHECK, read_only=True):
            print(f"{row['quoi']:28s} {row['detail']}")
        return
    if len(sys.argv) < 2:
        raise SystemExit(__doc__)
    path = Path(sys.argv[1])
    res = run_sql(path.read_text(encoding="utf-8"))
    print("appliqué :", path)
    if isinstance(res, list):
        for row in res:
            print("  ", json.dumps(row, ensure_ascii=False)[:200])


if __name__ == "__main__":
    main()
