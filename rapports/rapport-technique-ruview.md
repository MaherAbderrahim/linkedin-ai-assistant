# Rapport technique — dépôt GitHub `ruvnet/RuView`

**Objet :** base factuelle pour une critique technique LinkedIn.
**Date d'audit :** 15 novembre 2026 (données de l'API GitHub et fichiers `main` à cette date).
**Méthode :** lecture directe du code source, des documents techniques et des benchmarks via l'API GitHub et `raw.githubusercontent.com` ; recherche web pour le contexte externe. Aucun chiffre cité ici n'est inventé : chaque affirmation renvoie à son fichier source, avec le statut reproductible / affirmé / non vérifié.

**Convention d'étiquetage** (celle du dépôt lui-même, reprise ici) :
- **MEASURED** : mesuré par le projet et reproductible par le script fourni ;
- **CLAIMED** : affirmé, sans mesure associée ;
- **SYNTHETIC** : mesuré sur signal construit, pas sur données réelles ;
- **DATA-GATED / HARDWARE-GATED** : invérifiable sans données ou matériel spécifique ;
- **non vérifié** : que cet audit n'a pas pu vérifier.

---

## 1. Identité du dépôt et méthodologie d'audit

Sources : [API GitHub du dépôt](https://api.github.com/repos/ruvnet/RuView), [arborescence complète](https://api.github.com/repos/ruvnet/RuView/git/trees/main?recursive=1) (4 834 entrées, `truncated:false`), [LICENSE](https://github.com/ruvnet/RuView/blob/main/LICENSE).

| Propriété | Valeur (API GitHub, 15 nov. 2026) |
|---|---|
| Nom actuel | `RuView` (ancien nom : `wifi-densepose`) |
| Créé le | 7 juin 2025 |
| Stars / forks | 104 337 / 13 575 |
| Issues ouvertes | 588 |
| Licence | MIT (fichier LICENSE, 1 059 octets) |
| Branche par défaut | `main` |
| Site annoncé | cognitum.one |
| Langages | Rust dominant (~13 Mo), Python (~3 Mo), JavaScript (~3 Mo), ~18 langages au total |
| Fichiers | 3 992 fichiers blob |
| Topics | incluent `esp32`, `wifi`, `pose-estimation` |

**Distinction importante pour la critique :** le projet porte sur la *détection de présence* (savoir si quelqu'un est là), la *pose estimation* (où sont les articulations) et les *signes vitaux* (respiration, rythme cardiaque). Ce sont trois tâches de difficulté très inégale, et le dépôt lui-même finit par le dire. Ne pas confondre non plus *accuracy* (proportion de bonnes réponses) et *précision* (qualité de la mesure continue d'un angle ou d'une fréquence) : les chiffres du dépôt mélangent les deux notions selon la tâche, et le rapport suivant les sépare à chaque fois.

## 2. Contexte : de `wifi-densepose` à `RuView`, une réputation virale contestée

Le dépôt s'appelait à l'origine `wifi-densepose` — une référence directe au modèle DensePose de Meta (pose Corporelle à partir d'images), transposée au Wi-Fi. Il est devenu viral début 2026 sur cette promesse (« voir à travers les murs avec des ESP32 »), avec environ 23 000 stars en mars 2026 selon [un article de cybernews.com (mars 2026)](https://www.cybernews.com/news/wifi-densepose-github-project-ai-slop/) qui le qualifie « at best proof of concept » ; **aujourd'hui 104 337 stars** (API GitHub ci-dessus).

La controverse publique est documentée par plusieurs éléments :
- Les issues #11, #12, #21 et #39 de l'époque (citées via un dépôt adversaire, [deletexiumu/wifi-densepose](https://github.com/deletexiumu/wifi-densepose)) reprochaient des promesses sans démonstrations ; **contenu original non relu à la date de l'audit, non vérifié dans le détail**.
- Des publications sur X affirmant que le compteur de stars était en partie « fake » (« 23K stars... fake ») ; **non vérifié** : aucune preuve d'achat de stars n'a été trouvée, et le passage de ~23k à ~104k étoiles en huit mois est plausible par effet viral sans être explicable par l'audit.
- L'auteur (Reuven Cohen, « ruvnet ») a répondu publiquement, notamment sur LinkedIn, et surtout *dans le dépôt lui-même* (voir sections 4 et 8) : PROOF.md, ADR-187 « honest labeling », retraits publics de chiffres. L'article de cybernews note d'ailleurs la réaction de l'auteur.
- L'issue externe la plus technique, [#509](https://github.com/ruvnet/RuView/issues/509) (utilisateur `hcwang`, mai 2026, personne non affiliée), teste le système avec 4× ESP32-S3 et conclut : « PoC scaffold », « real infrastructure vs mocked AI layer », pose non reproductible en conditions réelles. Le framework (ingestion CSI, mesh, stockage) fonctionne ; la couche IA embarquée non.

**Fait vérifié dans le dépôt :** le dépôt a réagi par des retraits publics et une infrastructure d'honnêteté (section 4), ce qui est inhabituel et distinct des accusations initiales.

## 3. Structure du dépôt : masses de code et organisation

Source : arborescence complète API GitHub (4 834 entrées, non tronquée).

| Répertoire | Contenu | Ordre de grandeur |
|---|---|---|
| `v2/` | 1 338 fichiers, ~70 crates Rust nommées `wifi-densepose-*` : signal, matériel (ESP32/Realtek/MediaTek/Qualcomm CSI), entraînement (MM-Fi, WiDar), vitals, physique, `occworld-candle`, `wasm-edge` | cœur du projet |
| `docs/` | 586 fichiers, dont **332 ADR** (Architecture Decision Records) | documentation décisionnelle massive |
| `benchmarks/` | `wiflow-std/`, `edge-latency/`, `edge-skills/`, avec `RESULTS.md` par dossier | preuves chiffrées |
| `firmware/` | 246 fichiers, dont `esp32-csi-node` | C embarqué pour ESP32 |
| `assets/` | 84 fichiers, images et SVG du README | visuels |
| `examples/`, `harness/`, `wifi-veil/`, `python/`, `references/`, `ui/mobile/` | exemples three.js, harness IA, console TUI « Veil », bindings Python | périphériques |

**Observation critique :** l'ampleur est réelle (milliers de fichiers Rust, tests unitaires partout) mais asymétrique. Une seule crate (`wifi-densepose-wasm-edge`) contient 105 « skills » numérotés et à elle seule plus de 600 tests, pendant que la chaîne pose→EMBARQUÉ, qui est la promesse d'origine, tient dans une seule crate de taille modeste avec des résultats sous la cible (section 8). Le volume documentaire (332 ADR) est lui-même une caractéristique à commenter : c'est plus que la plupart des projets de la Linux Foundation.

## 4. Ce que le projet annonce — et ce qu'il retire lui-même

Source principale : [README.md](https://github.com/ruvnet/RuView/blob/main/README.md) (76,9 Ko, 849 lignes), seconde source [PROOF.md](https://github.com/ruvnet/RuView/blob/main/PROOF.md).

Le README annonce : détection de présence par CSI Wi-Fi, respiration/rythme cardiaque, pose 17 keypoints, mesh de capteurs ESP32, 802.11bf (« Wi-Fi sensing » normatif), integration home-assistant, toolkit agents. Un tableau chiffré présente des métriques avec leur statut.

Deux sections du README sont atypiques et centrales pour la critique :

1. **« Model weights: what's real, what's not »** — classification des poids de modèles en trois tiers (réels téléchargeables, à entraîner, inexistants). Les poids de pose embarquée « cog » sont explicitement présentés comme entraînés sur données synthétiques, avec `confidence` typique 0,185.
2. **Retraits publics** : le chiffre « 100% presence » a été retiré au profit de **82,3 % (temporal-triplet, held-out)** ; le « 92.9 % PCK » interne a été retiré (la pose mesurée était constante) ; une section « Beta software » liste les limitations ; un disclaimer précise que le projet **n'est pas un dispositif médical**.

[PROOF.md](https://github.com/ruvnet/RuView/blob/main/PROOF.md) formalise la méthodologie MEASURED / CLAIMED / DATA-GATED / HARDWARE-GATED, fournit un script de reproduction ([`scripts/prove.sh`](https://github.com/ruvnet/RuView/blob/main/scripts/prove.sh)) et affiche 3 128 tests Rust. Il contient aussi des *négations honnêtes* : l'identification d'une personne nominative (reconnaissance d'identité) est déclarée **NON atteinte** avec un écart de 0,0005 au seuil — c'est-à-dire que le système ne sait pas dire « c'est Alice ».

**Ce que la critique LinkedIn doit dire :** c'est le seul grand dépôt viral connu de nous qui publie ses propres réfutations et négations. Cela ne valide pas les promesses restantes, mais change la nature de la critique : le problème n'est plus la fraude, c'est l'écart entre la réputation (qui date des premières semaines) et l'état réel actuel du dépôt.

## 5. Code réel vs placeholder : échantillonnage du code

Méthode : lecture de fichiers représentatifs de chaque chaîne critique. Le code n'est **pas** un placeholder global.

### 5.1 La chaîne pose embarquée est du vrai code — avec un vrai problème

[`v2/crates/cog-pose-estimation/src/inference.rs`](https://github.com/ruvnet/RuView/blob/main/v2/crates/cog-pose-estimation/src/inference.rs) (17,3 Ko) : un vrai moteur d'inférénce Candle, architecture Conv1d (56→64→128→128) + MLP (128→256→34→sigmoid) qui produit 17 keypoints × 2 coordonnées. Le mode « stub » (confidence = 0) n'est actif **que si les poids sont absents** — comportement documenté, pas une triche. La constante `MODEL_TYPICAL_CONFIDENCE = 0.185` est honnête : le modèle lui-même « avoue » une confiance moyenne de 18,5 %.

### 5.2 Le DSP des signes vitaux est du vrai code, soigné

[`v2/crates/wifi-densepose-vitals/src/breathing.rs`](https://github.com/ruvnet/RuView/blob/main/v2/crates/wifi-densepose-vitals/src/breathing.rs) : filtre passe-bande IIR d'ordre 2 sur la bande **0,1–0,5 Hz** (6–30 respirations/min), extraction par passages à zéro, confiance par autocorrélation normalisée, défauts ESP32 (56 sous-porteuses, 100 Hz, fenêtre 30 s), et des tests de régression qui corrigent trois bugs réels référencés (ADR-157 §A2/A3, ADR-158 §A1, issue #1422 — verrouillage périmé quand le sujet quitte la pièce, empoisonnement NaN du filtre). C'est du code de production, pas de la démo.

### 5.3 Les fixtures étiquetées honnêtement

[`v2/crates/wifi-densepose-mtk-bridge/fixtures/`](https://github.com/ruvnet/RuView/tree/main/v2/crates/wifi-densepose-mtk-bridge/fixtures) : des jeux de données de test sont étiquetés **« FABRICATED »** dans le nom du fichier — une pratique de transparence rare, mais qui confirme aussi que certains flux matériels (Realtek/MediaTek) sont testés sur des données synthétiques, faute de matériel réel de ces constructeurs.

**Bilan :** le code est réel, testé, souvent de bonne qualité. Le problème documenté n'est pas du code mort, mais un modèle entraîné sur des données insuffisamment réalistes (section 8) et des promesses périphériques non mesurées (sections 9-10).

## 6. Matériel requis et firmware ESP32

Source principale : [`firmware/esp32-csi-node/README.md`](https://github.com/ruvnet/RuView/blob/main/firmware/esp32-csi-node/README.md) (1 232 lignes).

- **Matériel :** ESP32-S3 (taré **7–9 $** la carte par le README), ESP32-C6 ou C5. C'est le seul point d'entrée matériel, réellement accessible.
- **Firmware :** C embarqué avec interpréteur WASM3, quatre tiers (0-3) de capacités croissantes. Extraction CSI réelle documentée.
- **Section « What this firmware does NOT do »** (le README du firmware se corrige lui-même) :
  - le **comptage de personnes** est une heuristique de « slot capacity » ([`edge_processing.c`, ligne 481](https://github.com/ruvnet/RuView/blob/main/firmware/esp32-csi-node/src/edge_processing.c)), pas un modèle neuronal ;
  - **pas de pose** sur l'ESP32 lui-même (la pose tourne sur un hôte) ;
  - la **présence** peut produire des **faux positifs RF** (courants d'air, objets en mouvement, autres sources 2,4/5 GHz) — le firmware le dit explicitement ;
  - renvoi à l'[issue #2287](https://github.com/ruvnet/RuView/issues/2287) pour les limitations détaillées.

**Pour la critique :** le matériel est bon marché et réel, mais le firmware embarqué seul ne fait ni pose ni comptage fiable — les fonctions marketing phares sont hébergées ailleurs ou heuristiques.

## 7. Présence et signes vitaux : ce qui est implémenté

### 7.1 Présence : MEASURED, mais sur des conditions favorables

- **82,3 %** (détection de présence, méthode « temporal-triplet », jeu de test held-out) — [README.md](https://github.com/ruvnet/RuView/blob/main/README.md), en remplacement du « 100 % » retiré. Statut : MEASURED selon PROOF.md, reproductible par `scripts/prove.sh`. **Non re-exécuté par cet audit** (matériel requis).
- C'est de la détection binaire de présence, **pas de l'identification** : PROOF.md précise que l'identité nominative n'est pas atteinte (écart 0,0005).

### 7.2 Signes vitaux : code réel, étiqueté « experimental »

- Le [code de respiration](https://github.com/ruvnet/RuView/blob/main/v2/crates/wifi-densepose-vitals/src/breathing.rs) est réel (section 5.2) avec bande 0,1–0,5 Hz confirmée dans le code.
- Le README qualifie lui-même les signes vitaux d'**experimental** et interdit l'usage médical (disclaimer « not medical devices »).
- Aucune mesure d'erreur absolue (± respirations/min) sur CSI réel n'est publiée dans les documents lus ; les chiffres disponibles sont **synthétiques** (section 9).

**Distinction clé pour LinkedIn :** 82,3 % de détection de présence est un chiffre honnête mais faible pour un produit ; un détecteur PIR à 15 € fait mieux sur ce seul critère. La valeur ajoutée annoncée (sans caméra, sans contact) est réelle, mais le chiffre à retenir est « présence pas identification, pas médical ».

## 8. Pose estimation : l'écart central entre publié et mesuré

C'est le dossier le plus sévère du dépôt — et le plus intéressant.

### 8.1 Le checkpoint upstream réfuté

[`benchmarks/wiflow-std/RESULTS.md`](https://github.com/ruvnet/RuView/blob/main/benchmarks/wiflow-std/RESULTS.md) :
- Le checkpoint WiFlow-STD publié en amont annonce **PCK@20 = 97,25 %**. Mesuré par le projet sur le même protocole : **0,08 %** — statut **REFUTED**, documenté noir sur blanc.
- Un ré-entraînement par le projet atteint ~**96,6 %**, validant que la *méthode* est reproduisible mais que le checkpoint publié ne l'était pas.
- Le chiffre interne « 92,9 % PCK » a été **retiré** : la pose mesurée était constante (le modèle prédisait toujours la même chose).
- Un dataset corrompu (NaN) est documenté dans le même fichier.

### 8.2 L'étude MM-Fi : les vrais chiffres et leurs conditions

[`docs/benchmarks/mmfi-wifi-sensing-study.md`](https://github.com/ruvnet/RuView/blob/main/docs/benchmarks/mmfi-wifi-sensing-study.md), sur le dataset réel [MM-Fi (NeurIPS 2023, arXiv 2305.10345)](https://arxiv.org/abs/2305.10345) :

| Protocole | Torso-PCK@20 | Lecture honnête |
|---|---|---|
| `random_split` (single) | **82,69 %** | condition favorable |
| `random_split` (ensemble) | **83,59 %** | condition favorable |
| cross-subject | **64 %** | généralisation à une nouvelle personne |
| cross-environment | **~10 %** | quasi-échec dans une nouvelle pièce |
| action (in-domain) | 88,1 % | — |
| action (cross-subject) | **10 %** | quasi-échec |

L'étude elle-même note que le résultat ressemble à « **random features + readout** » (caractéristiques quasi aléatoires + couche de lecture) et que la calibration **few-shot dans la pièce** est nécessaire. Le contexte académique confirme que la tâche est réelle et active (voir [MultiFormer, arXiv 2505.22555](https://arxiv.org/abs/2505.22555), pose CSI multi-personne ; [Person-in-WiFi 3D, CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Dong_Person-in-WiFi_3D_CVPR_2024_paper.pdf)) — RuView ne rivalise simplement pas avec eux hors de la pièce calibrée.

### 8.3 La pose embarquée : sous la cible, assumé

[`docs/benchmarks/pose-estimation-cog.md`](https://github.com/ruvnet/RuView/blob/main/docs/benchmarks/pose-estimation-cog.md) :
- `cog pose_v1` : **PCK@20 = 3,0 %**, PCK@50 = 18,5 %, sur 217 échantillons — **sous la cible ADR-079 de ≥35 %**, ce qui est documenté comme un échec.
- Raspberry Pi 5 : 8,4 ms de cold-start mesurés ; chaîne GCS signée Ed25519.

**Pour la critique :** le projet d'origine promettait le DensePose Wi-Fi. Aujourd'hui, la pose sous 35 % de PCK@20 embarquée ne fonctionne pas, et la pose sur dataset ne fonctionne que dans la pièce calibrée. Le projet le dit — c'est le paradoxe central : réfutation honnête d'une promesse virale jamais tenue.

## 9. Edge skills : validation synthétique et liste DATA-GATED

Source : [`benchmarks/edge-skills/RESULTS.md`](https://github.com/ruvnet/RuView/blob/main/benchmarks/edge-skills/RESULTS.md) (13 juin 2026, ADR-160).

Ce fichier commence par un avertissement « HONESTY BOUNDARY » : tout ce qui suit est une **validation à vérité-terrain synthétique** — un signal est *planté* avec une réponse connue, le détecteur réel tourne, la détection est mesurée. « Ceci n'est PAS de la précision en conditions réelles. »

- **MEASURED-on-synthetic** : 12 skills (vital_trend, exo_time_crystal, occupancy, intrusion, exo_rain_detect, etc.) avec accuracy **1.000** chacun — sur des signaux construits par le harnais lui-même. Autrement dit : le code fait le calcul qu'il prétend faire, rien de plus.
- **Resultat négatif assumé** : `sig_sparse_recovery` — la RMSE *après* « récupération » est **1,0045 contre 0,9830 sans récupération (−2,2 %, légèrement pire que de ne rien faire)**. Publié tel quel.
- **DATA-GATED (aucun chiffre)** : détection de crise épileptique, arme, émotion, stade de sommeil, langue des signes — le fichier explique *pourquoi* un signal synthétique « ressemblant » ne prouverait rien, et liste les données cliniques réelles nécessaires à chaque cas. Citation : c'est « exactly the AI-slop this project fights ».
- Tests de la crate : **631 passés (std) / 669 (medical tier)**, 0 échec — mais les skills médicaux restent non validés.

**Pour la critique :** un « accuracy 1.000 » sur signal planté ne vaut pas plus que « le test unitaire passe ». Le dépôt le dit lui-même ; toute reprise du chiffre 1.000 sans le contexte synthétique serait précisément le type de désinformation que le projet prétend combattre.

## 10. Latences edge annoncées vs reproduites

Source : [`benchmarks/edge-latency/RESULTS.md`](https://github.com/ruvnet/RuView/blob/main/benchmarks/edge-latency/RESULTS.md).

- Les chiffres publiés (17,3 µs pour `exo_time_crystal`, cogs ~305 µs steady-state) sont des mesures **sur l'hôte**, pas sur l'ESP32.
- Le fichier le dit explicitement : le budget de latence **ESP32 est « NOT reproduced »** — les performances embarquées annoncées restent HARDWARE-GATED.
- Toute latence « edge » du projet est donc à citer comme *hôte*, sauf preuve contraire sur carte réelle.

## 11. Limitations documentées, réception externe et crédibilité

### 11.1 Limitations écrites par le projet lui-même

- README section « Beta software » + disclaimer « not medical devices » ;
- firmware : « What this firmware does NOT do » (section 6) ;
- PROOF.md : négations (identité non atteinte) ;
- edge-skills : « HONESTY BOUNDARY » (section 9) ;
- edge-latency : « NOT reproduced » (section 10).

### 11.2 Réception externe

- **Issue #509** ([hcwang, mai 2026](https://github.com/ruvnet/RuView/issues/509)) : infrastructure réelle, couche IA simulée côté embarqué ; pose non reproductible avec 4× ESP32-S3. C'est le témoignage externe le plus technique et il est cohérent avec ce que le dépôt avoue.
- **Article [cybernews.com](https://www.cybernews.com/news/wifi-densepose-github-project-ai-slop/) (mars 2026)** : « at best proof of concept », reprend les issues #11/#12/#21/#39.
- **Démo vs réalité :** l'[issue #509](https://github.com/ruvnet/RuView/issues/509) confirme que le squelette animé visible en démo tourne en « **simulation mode** » sans matériel — le README lui-même qualifie la pose live single-ESP32 de « first-cut, below-target, runtime-stub ».
- **Stars** : 104 337 (API), en croissance depuis ~23k en mars 2026 ; soupçon d'inflation exprimé sur X, **non vérifié**, aucune preuve trouvée.

### 11.3 Bilan de crédibilité

Le dépôt a franchi un seuil rare : il publie ses réfutations (WiFlow-STD REFUTED, retrait de « 100 % », retrait de « 92,9 % », récupération pire que l'abstention). La critique honnête n'est donc plus « c'est de la fumée » mais « la réputation (104k étoiles, promesse DensePose-Wi-Fi) est en avance de plusieurs années sur le contenu (présence à 82,3 % en condition favorable, pose 3 % embarquée, vitaux non validés sur CSI réel) ».

## 12. Images et supports visuels vérifiés

**Existence prouvée** par l'arborescence API (41 fichiers png/jpg/gif, plus ~70 SVG dans `assets/readme/`, décrits par [`assets/readme/manifest.json`](https://github.com/ruvnet/RuView/blob/main/assets/readme/manifest.json)). **URLs brutes testées une par une** (GET, 15 nov. 2026) — les 12 vérifiées répondent toutes HTTP 200 :

| Image (URL brute vérifiée) | Statut | Taille | Rôle (d'après le README/manifeste) |
|---|---|---|---|
| [`assets/ruview-hero-h3-v3.gif`](https://raw.githubusercontent.com/ruvnet/RuView/main/assets/ruview-hero-h3-v3.gif) | 200 | 5,77 Mo | bannière animée du README |
| [`assets/v2-screen.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/assets/v2-screen.png) | 200 | 4,19 Mo | capture d'écran de l'interface v2 |
| [`assets/screenshot.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/assets/screenshot.png) | 200 | 410 Ko | capture d'écran |
| [`assets/ruview-seed.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/assets/ruview-seed.png) | 200 | 2,0 Mo | visuel « Cognitum seed » |
| [`assets/screen.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/assets/screen.png) | 200 | 276 Ko | capture d'écran |
| [`docs/archtocode-visual-overview/hight-level-flow-architecture.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/docs/archtocode-visual-overview/hight-level-flow-architecture.png) | 200 | 1,31 Mo | schéma d'architecture (titre mal orthographié : « hight ») |
| [`examples/three.js/screenshots/05-skinned-realtime.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/examples/three.js/screenshots/05-skinned-realtime.png) | 200 | 610 Ko | rendu three.js « skinned realtime » |
| [`references/densepose_performance_chart.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/references/densepose_performance_chart.png) | 200 | 199 Ko | graphique de performance DensePose (référence académique) |
| [`references/wifi-densepose-arch.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/references/wifi-densepose-arch.png) | 200 | 1,14 Mo | schéma d'architecture wifi-densepose (référence) |
| [`v2/crates/wifi-densepose-privshield/docs/veil-console.png`](https://raw.githubusercontent.com/ruvnet/RuView/main/v2/crates/wifi-densepose-privshield/docs/veil-console.png) | 200 | 310 Ko | console du module vie privée « Veil » |
| [`wifi-veil/docs/assets/veil-tui.gif`](https://raw.githubusercontent.com/ruvnet/RuView/main/wifi-veil/docs/assets/veil-tui.gif) | 200 | 116 Ko | interface TUI animée « Veil » |
| [`assets/readme/hero-spatial-v6.svg`](https://raw.githubusercontent.com/ruvnet/RuView/main/assets/readme/hero-spatial-v6.svg) | 200 | 3,2 Ko | bannière SVG du README (titre : « RuView: invisible signals, visible possibility ») |

**Précaution pour l'usage LinkedIn :** ces descriptions de rôle proviennent du README et du manifeste, pas d'une inspection pixel par pixel des images par cet audit. Les captures d'écran de pose (`v2-screen.png`, `05-skinned-realtime.png`) montrent l'interface en mode qui peut être **simulation** (cf. issue #509) — à ne pas présenter comme des preuves de détection réelle. La licence MIT du dépôt autorise la réutilisation avec attribution (« ruvnet/RuView »).

## 13. Licence, réutilisabilité et positionnement

- **Licence MIT** ([LICENSE](https://github.com/ruvnet/RuView/blob/main/LICENSE), 1 059 octets) : code et images réutilisables librement avec attribution.
- **Poids de modèles** : le README distingue trois tiers de disponibilité ; certains poids réels sont annoncés sur [huggingface.co/ruvnet/wifi-densepose-pretrained](https://huggingface.co/ruvnet/wifi-densepose-pretrained) (lien du manifeste des assets ; **disponibilité effective non vérifiée par cet audit**).
- **Positionnement honnête à retenir :** un framework de recherche open-source sur la perception Wi-Fi (ingestion CSI multi-constructeurs, DSP vital, mesh ESP32, outillage d'honnêteté expérimental), pas un produit de « vision à travers les murs ». La norme 802.11bf (Wi-Fi sensing) est mentionnée mais les documents lus ne montrent aucune implémentation 802.11bf mesurée — **annoncé seulement**.
- **Comparaison académique :** le domaine est réel et actif (MM-Fi/NeurIPS 2023, MultiFormer/2025, Person-in-WiFi 3D/CVPR 2024) ; RuView n'est pas l'état de l'art, c'est un outil exploratoire avec une documentation d'honnêteté inhabituelle.

---

## Conclusion honnête

RuView est le dépôt le plus documenté que nous ayons vu sur la perception Wi-Fi open-source, et le seul de cette taille à publier ses propres réfutations : le checkpoint WiFlow-STD annoncé à 97,25 % de PCK@20 est mesuré à 0,08 % et étiqueté REFUTED, le « 100 % presence » a été retiré au profit de 82,3 %, et la pose embarquée est assumée à 3,0 % de PCK@20, sous la cible du projet lui-même. Le code Rust est massif, réel et testé (3 128 tests revendiqués, DSP vital de qualité production), mais l'essentiel des métriques flatteuses est soit synthétique (skills edge à 1.000 sur signaux plantés, explicitement « NOT field accuracy »), soit limité à la pièce calibrée (cross-environnement ~10 %). Les fonctions phares du firmware — comptage de personnes et pose — sont une heuristique et un mode simulation, comme le confirme le témoignage externe de l'issue #509 avec 4× ESP32-S3. La réputation publique, forgée début 2026 sous le nom wifi-densepose et aujourd'hui portée par 104 337 étoiles, décrit un projet qui n'existe pas encore ; le dépôt actuel décrit honnêtement un framework de recherche en phase bêta, utile pour l'ingestion CSI, le DSP vital et la méthodologie d'évaluation. La promesse d'origine — voir le corps à travers les murs avec des cartes à 8 $ — n'est ni réalisée ni réaliste dans l'état documenté, et le projet l'écrit lui-même à plusieurs endroits. Pour une critique LinkedIn, la ligne honnête est donc double : ne pas répéter la promesse virale, mais créditer la rareté du processus de réfutation publique, qui est précisément ce que les « AI slop » ne font jamais. Les chiffres à citer sans détour : 82,3 % de présence en condition favorable, 3,0 % de PCK@20 embarqué, ~10 % hors pièce calibrée, tout le reste étant annoncé, synthétique ou hardware-gated.

---

### Sources principales

- Dépôt : https://github.com/ruvnet/RuView (API : https://api.github.com/repos/ruvnet/RuView)
- README : https://github.com/ruvnet/RuView/blob/main/README.md
- PROOF.md : https://github.com/ruvnet/RuView/blob/main/PROOF.md
- Benchmarks : [`wiflow-std`](https://github.com/ruvnet/RuView/blob/main/benchmarks/wiflow-std/RESULTS.md) · [`edge-latency`](https://github.com/ruvnet/RuView/blob/main/benchmarks/edge-latency/RESULTS.md) · [`edge-skills`](https://github.com/ruvnet/RuView/blob/main/benchmarks/edge-skills/RESULTS.md)
- Études : [`mmfi-wifi-sensing-study.md`](https://github.com/ruvnet/RuView/blob/main/docs/benchmarks/mmfi-wifi-sensing-study.md) · [`pose-estimation-cog.md`](https://github.com/ruvnet/RuView/blob/main/docs/benchmarks/pose-estimation-cog.md)
- Code : [`inference.rs`](https://github.com/ruvnet/RuView/blob/main/v2/crates/cog-pose-estimation/src/inference.rs) · [`breathing.rs`](https://github.com/ruvnet/RuView/blob/main/v2/crates/wifi-densepose-vitals/src/breathing.rs)
- Firmware : [`firmware/esp32-csi-node/README.md`](https://github.com/ruvnet/RuView/blob/main/firmware/esp32-csi-node/README.md)
- Issues : [#509](https://github.com/ruvnet/RuView/issues/509) · [#2287](https://github.com/ruvnet/RuView/issues/2287)
- Presse : [cybernews.com, mars 2026](https://www.cybernews.com/news/wifi-densepose-github-project-ai-slop/)
- Académique : [MM-Fi, arXiv 2305.10345](https://arxiv.org/abs/2305.10345) · [MultiFormer, arXiv 2505.22555](https://arxiv.org/abs/2505.22555) · [Person-in-WiFi 3D, CVPR 2024](https://openaccess.thecvf.com/content/CVPR2024/papers/Dong_Person-in-WiFi_3D_CVPR_2024_paper.pdf)
