# 🐍 Mémoire d'Instructions - Projet MagicPython

Ce document retrace l'ensemble des fonctionnalités implémentées, des choix techniques et des déploiements réalisés pour le projet "MagicPython", un jeu d'apprentissage du code en Python, intégré discrètement au site OhVali (AI News).

## 1. Structure Initiale et Technologies
- **Framework** : React + Vite.JS.
- **Stylisation** : Tailwind CSS + Lucide React (icônes).
- **Moteur d'Exécution** : Intégration de **Pyodide** (permettant d'exécuter du code Python directement dans le navigateur du client sans serveur backend).
- **Interface Principale** : `App.jsx`, contenant un éditeur de texte interactif synchronisé, une console de sortie, la section théorie/instructions, et un menu de sélection des quêtes.

## 2. Création et Fractionnement des 100 Niveaux
- Extension de la base de données initiale de 30 niveaux.
- Le jeu comporte désormais **100 quêtes** à difficulté croissante pour apprendre de zéro jusqu'aux algorithmes experts et la création d'un mini-moteur RPG.
- Pour des raisons de performance et de lisibilité de code, découpés en 4 modules distincts :
  - `basics.js` : Niveaux 1 à 30 (Variables, conditions, listes).
  - `intermediate.js` : Niveaux 31 à 60 (Dictionnaires, sets, lambda, lecture/écriture de fichiers).
  - `advanced.js` : Niveaux 61 à 80 (Programmation Orientée Objet avancée, propriétés, générateurs, itertools).
  - `expert.js` : Niveaux 81 à 100 (Expressions régulières, Coroutines asynchrones, Récursivité, Tri, Arbres, Métaclasses).
  
## 3. Améliorations de l'Interface Utilisateur (UI/UX)
- Modification de la structure de l'application en limitant la hauteur `h-screen` pour **bloquer le défilement (scroll) global** de la page web.
- Seuls les panneaux intérieurs (liste des niveaux, théorie, terminal, éditeur) ont leur propre défilement indépendant (`overflow-y-auto`).
- Ajout de barres de défilement (scrollbars) personnalisées et élégantes (CSS custom).
- Intégration de suggestions automatiques au clavier et indentation.

## 4. Persistance des Données (Sauvegarde)
- Intégration du `localStorage` du navigateur pour la sauvegarde de la progression du joueur.
- Conservation de trois variables locales essentielles pour une reprise ultérieure :
  - L'index du dernier niveau sur lequel le joueur était (`magicpython_level`).
  - L'expérience / XP du joueur (`magicpython_xp`).
  - La variable listant les niveaux débloqués (`magicpython_unlocked`).

## 5. Le Bilinguisme (FR / EN)
- Intégration d'un système bilingue gérable avec une sauvegarde `localStorage` (`magicpython_lang`).
- Toute l'interface (UI) est réactive selon le choix (boutons, aides, chargement, messages d'erreur).
- Rédaction d'un script Node (`script_translate.mjs`) exploitant l'API Google Translate Asynchrone.
- Ce script a permis la **traduction stricte et complète** (sur les 100 niveaux) des descriptions, théories, objectifs, et commentaires du code sans altérer le coeur python.
- Les propriétés `*_en` (`title_en`, `story_en`, etc.) sont injectées dynamiquement si la langue choisie est l'Anglais.

## 6. L'Hébergement et la Stratégie de Déploiement
- Le projet local Vite/React n'a pas été publié comme un repository séparé. Il est considéré comme un sous-projet du site de news.
- Modification du `vite.config.js` pour utiliser le pointeur racine `base: '/magicpython/'`.
- Exécution de commandes de Build de production : le résultat optimisé (fichiers compilés statiques : HTML/JS/CSS) a été injecté dans le dossier `magicpython` du site **ia-news**.
- Push automatique sur la branche Github (repository `valerium-ai-news`) à l'aide du jeton du développeur, mais en garantissant **qu'aucun token ou clé secrète** ne soit mis en clair dans les fichiers source envoyés sur Github.
- Le jeu est désormais accessible en ligne via GitHub Pages.

## 7. L'Easter Egg
- Afin de faire un pont depuis OhVali.com, un lien ultra caché a été créé dans le bas de page du site d'actualités.
- Un petit émoji serpent "🐍" quasi invisible (opacité à 2%) est cliquable dans le footer du fichier `index.html` de base (le site des News), pointant vers `/magicpython/`, servant d'entrée secrète pour les mages apprentis.
