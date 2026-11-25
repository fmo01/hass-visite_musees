# Visite Musées — v0.1.12

Intégration personnalisée Home Assistant distribuable par HACS. Le domaine est **`visite_musees`** et la version du manifeste est **`0.1.12`**.

## Nouveautés

- Identifiants techniques de l'intégration, du panneau et des WebSocket renommés intégralement.
- Endpoints publics, chemins du panneau et clés de stockage centralisés dans `custom_components/visite_musees/const.py`.
- `frontend/i18n.js` charge les langues par URL relative, indépendamment du chemin statique.
- Versions JavaScript dérivées du manifeste ; trace `VISITE MUSEES v0.1.12`.
- Référentiel Muséofile national, API Géo, catalogue et historique de visites inchangés dans leur comportement prévu.

## Installation / changement de domaine

⚠️ **Ce changement de domaine nécessite une nouvelle installation HA** : le simple remplacement de dossier dans HACS ne modifie pas l'entrée de configuration existante. Ne pas supprimer les données avant d'avoir effectué une sauvegarde complète.

1. Faire une sauvegarde complète de Home Assistant, comprenant le dossier caché `.storage`.
2. Noter les départements sélectionnés ; retirer l'intégration précédente dans **Appareils et services** (les entités précédentes seront recréées avec de nouveaux identifiants techniques).
3. Installer le contenu de cette archive via ton dépôt HACS, dans `custom_components/visite_musees/` ; retirer l'ancien dossier `custom_components` de l'intégration précédente. Redémarrer HA.
4. Ajouter **Visite Musées** dans Appareils et services, puis sélectionner les départements.
5. Pour récupérer les données personnelles, arrêter HA, exécuter l'utilitaire de migration **fourni séparément** (d'abord sans `--apply`, puis avec `--apply`) et redémarrer HA.
6. Vérifier les favoris et visites dans le panneau `/visite-musees`. Vérifier ou recréer les automatisations et tableaux de bord qui utilisaient les anciennes entités.

Le script de migration n'est pas fourni dans l'archive HACS : il sert uniquement à copier les anciens fichiers de stockage vers les nouvelles clés, **sans modifier** les entrées de configuration ni les registres HA. Il n'écrase aucun fichier de destination déjà présent. Pour migrer des données vers une nouvelle entrée déjà initialisée, vérifier d'abord si le stockage cible contient des choix à conserver.

## Développement

```bash
python -m pytest tests/ -q
```

La collecte des expositions MAD et Orsay reste expérimentale. Le blocage serveur HTTP 403 d'Orsay n'est pas corrigé par cette version.

Voir [ROADMAP.md](ROADMAP.md) pour la suite du projet.
