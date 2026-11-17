"""Lanceur pour hébergement managé (type Pterodactyl/Pelican) : démarre l'assistant.

Le panneau exécute un fichier unique (par défaut app.py) à la racine du conteneur.
Ce lanceur :
- ajoute src/ au chemin d'import (layout src, aucune installation pip nécessaire :
  le projet n'a aucune dépendance d'exécution sous Linux) ;
- crée le dossier de la base SQLite ;
- sans config.toml, copie config.example.toml (mode simulation, aucun envoi externe) ;
- les secrets restent dans .env (config.toml → env_file) ou dans les variables
  d'environnement du panneau — jamais dans ce fichier.
"""

import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "src"))
local_bin = ROOT / ".local" / "bin"
if local_bin.is_dir():
    os.environ["PATH"] = str(local_bin) + os.pathsep + os.environ.get("PATH", "")

os.makedirs(ROOT / "data", exist_ok=True)

config_path = ROOT / "config.toml"
if not config_path.exists():
    example = ROOT / "config.example.toml"
    if example.exists():
        shutil.copyfile(example, config_path)

from linkedin_assistant.app import main  # noqa: E402

raise SystemExit(main())
