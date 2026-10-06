# INDEX du savoir — « pour trouver X → fichier Y »

> Routeur du socle. Rangé **par question**, pas par document. Lu directement par les skills (jamais
> vectorisé). Les livres et formations de Loïc (scans) sont dans la base Supabase `savoir_*`
> (skill `froid-savoir`, Lot 4) ; ici ne vit que le savoir distillé, maintenu par Adrien.
> État : **v2 (Lot 2, 2026-10-06)** : fluides, règlement F-gas, méthode de puissance, règles de Loïc,
> transitions, fiche Bitzer.

| Question | Fichier | Remarque |
|---|---|---|
| Qu'est-ce qu'un relevé complet ? Qu'est-ce qui doit être demandé à Loïc s'il manque ? | `methodes/checklist-releve.md` | Même liste que les « infos indispensables » de la variante E de `resume-vocal-devis` : les deux restent synchronisées |
| Comment lire une plaque signalétique de compresseur / groupe / évaporateur ? | `materiel/lecture-plaques.md` | v1 générale ; compléments par marque dans `materiel/<marque>.md` |
| Comment décoder une référence Bitzer, où trouver ses données, à quelles conditions ? | `materiel/bitzer.md` | Codes de série et moteur, volumes balayés, conditions EN 12900 des données Bitzer |
| Comment se déroule l'étape 2 (dimensionnement) : format de `2-entrees.json`, calcul, livrable, vérificateur ? | `.claude/skills/froid-dimensionnement/SKILL.md` | `scripts/calculs.py` produit `2-resultats.json` et les tableaux B, C, D ; vue HTML par `shared/rendu_html.py` |
| Quelle puissance frigorifique pour un compresseur donné à un régime donné ? | `methodes/puissance-existante.md` | Deux méthodes : M1 par la cylindrée (table de λ sourcée), M2 par le point catalogue corrigé ; statuts ; exemple chiffré |
| Quelle puissance a publié le fabricant pour tel modèle, à quel régime ? | `materiel/points-catalogue/<marque>-<fluide>.csv` | Points nominaux avec conditions, lien et date de lecture (fichiers créés par un autre sous-agent du Lot 2) |
| Quelle puissance pour une chambre froide selon son volume ? | — | **Contrôle par le volume : pas d'abaque en V1 (décision du 2026-10-06)** ; options futures dans le plan privé. Pas de bilan thermique détaillé en V1 |
| Quel PRP (GWP) pour un fluide ou un mélange, quelle classe de sécurité ? | `fluides/prp.csv`, `fluides/compositions-melanges.csv` | PRP du règlement (UE) 2024/573 : AR4 pour les HFC, AR6 pour les HFO ; mélanges recalculés (annexe VI) |
| Quel fluide est encore autorisé : entretien, mise sur le marché, contrôles d'étanchéité ? | `fluides/reglementation-fgas.csv` | **Table non relue** : à relire par Adrien sur EUR-Lex avant mise en service (colonnes `relu_par`, `date_relecture`) |
| Que garde-t-on, que remplace-t-on quand on change de fluide ? | `methodes/transitions.md` | HFC → CO2 booster, HFC → HFC/HFO (retrofit), HFC → propane ; à compléter avec Loïc |
| Quelles sont les règles de pouce de Loïc (régimes, marges, seuils, marques, régulation) ? | `methodes/regles-loic.md` | Datées et sourcées ; réponses aux six questions du 2026-10-06 ajoutées en fin de fichier |
