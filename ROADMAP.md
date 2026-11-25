# Roadmap — Visite Musées

## Principes validés

- Domaine technique unique : `visite_musees` ; présentation : **Visite Musées**.
- Muséofile national via l'API tabulaire de data.gouv.fr, sans référentiel local de musées.
- Départements chargés depuis l'API Géo officielle ; sélection multiple dans les options.
- Favoris, masquages et visites planifiées/effectuées conservés indépendamment des flux d'expositions.
- Interface dédiée dans la barre latérale, traduction française, anglaise et espagnole.
- Versions de maintenance `0.1.x` jusqu'à nouvel arbitrage ; archives HACS sans fichiers de cache Python.

## Lots

| Lot | Objet | État | Prochaine action |
|---|---|---|---|
| 01 | Référentiel national Muséofile + pagination JSON | Validé sur HA OS en v0.3.11 | Surveiller la fraîcheur et les erreurs API |
| 02 | Départements administratifs via API Géo | Fonctionnel (v0.3.12) | Vérifier choix, multi-départements et cache |
| 03 | Renommage intégral, constantes communes, migration | Livré pour validation (v0.1.12) | Valider une migration réelle avec sauvegarde |
| 04 | Collecteurs d'expositions MAD / Orsay | À corriger | Adapter le MAD ; tester l'accès Orsay avec `curl_cffi` (HTTP 200 observé hors HA) |
| 05 | Extension des sources d'expositions nationales | À faire | Identifier les sources officielles exploitables par musée |
| 06 | Panneau de consultation et parcours des visites | Fonctionnel, améliorable | Ergonomie, recherche, archives, statuts de collecte |
| 07 | Internationalisation et qualité | En cours | Étendre les traductions, tests HA et contrôle des journaux |
| 08 | Publication et maintenance HACS | À poursuivre | Procédure de migration, releases, tests, CI |

## Décisions et risques

- Changer le domaine HA exige une nouvelle entrée de configuration ; les données personnelles stockées sous l'ancien domaine ne basculent pas toutes seules.
- Les expositions collectées restent partielles ; Muséofile répertorie les établissements, pas leur programmation.
- Le refus HTTP 403 d'Orsay avec `aiohttp` reste une limitation non résolue dans la présente version.
- Préserver le dernier cache valide si une source échoue ; ne pas confondre absence de résultat et échec de collecte.

## Critères de validation v0.1.12

1. L'intégration est détectée sous `visite_musees` et la barre latérale « Visite Musées » est présente.
2. Console : `VISITE MUSEES v0.1.12`.
3. Les départements sélectionnés et les musées nationaux s'affichent correctement.
4. Après migration hors ligne, favoris, masquages, visites planifiées et effectuées sont conservés.
5. Aucune ancienne référence technique de domaine n'est présente dans l'archive HACS.
