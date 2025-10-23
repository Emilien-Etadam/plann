# plann

plann est un client CalDAV qui combine :

- une interface en ligne de commande historique ;
- une mini application graphique CustomTkinter (mode dock) ;
- une saisie en langage naturel alimentee par Ollama (texte et voix).

## Fonctionnalites principales

- Connexion directe a nimporte quel serveur CalDAV (Nextcloud, Zimbra, Baikal...).
- Fenetre compacte toujours visible, avec historique repliable.
- Ajout dinformations en langage naturel et dictation (Ollama + SpeechRecognition).
- Routage automatique vers les collections CalDAV qui acceptent VEVENT ou VTODO.
- Compatibilite totale avec les commandes CLI `plann add`, `plann todo`, etc.

## Installation rapide

```bash
git clone https://github.com/tobixen/plann.git
cd plann
python -m venv .venv
. .venv/Scripts/activate    # PowerShell : .\.venv\Scripts\Activate.ps1
pip install -r requirements-ollama.txt
pip install -e .            # optionnel : mode developpement
```

### Activer la dictee (facultatif)

```bash
pip install SpeechRecognition pyaudio
```

Sous Windows, installe PortAudio (`pip install pipwin && pipwin install pyaudio`) ou utilise un binaire precompile.

### Installer Ollama

1. Telecharge Ollama : <https://ollama.ai> puis lance `ollama serve`.
2. Tire un modele : `ollama pull llama2` (ou un modele francophone).
3. Verifie que `http://localhost:11434` est accessible (parametrable dans la GUI).

## Utilisation

### Interface graphique

```bash
python -m plann.gui        # ou cree un alias plann-gui
```

- La touche **Entrer** valide immediatement l evenement ou la tache.
- Le bouton micro lance la dictee (15 s dattente, 25 s denregistrement).
- Lengrenage ouvre lassistant de configuration (CalDAV, Ollama).
- Lhistorique se replie via les fleches `v` / `^`.

### Ligne de commande

```bash
plann add event "Reunion sprint" 2025-05-02T14:00+2h
plann add todo "Preparer la presentation" --set-due 2025-05-01
plann agenda --config-section work
```

Consulte `USAGE.md` pour voir toutes les commandes disponibles.

### Langage naturel

```bash
python -m plann.ai_cli "Dentiste mardi prochain a 11h au 22 place de l'Europe"
```

La GUI utilise exactement la meme pipeline que cette commande.

## Configuration

Par defaut plann lit `~/.config/calendar.conf` (JSON ou YAML). Exemple minimal :

```json
{
  "default": {
    "caldav_url": "https://cal.example.com/remote.php/dav",
    "caldav_user": "alice",
    "caldav_pass": "motdepasse",
    "calendar_url": "perso"
  }
}
```

Les sections peuvent heriter (`inherits`) ou regrouper (`contains`) dautres sections. La GUI enregistre automatiquement la section `default` et identifie quelles collections acceptent VEVENT ou VTODO.

## Developpement

- Tests de syntaxe : `python -m compileall plann`
- Linting : a completer (contributions bienvenues)
- Pull requests : nouvelles integrations CalDAV, ameliorations GUI, packaging...

## Pistes doptimisation

1. Packaging multiplateforme (PyInstaller + Inno Setup, ou BeeWare Briefcase).
2. Memoire des habitudes (categorisation, durees par defaut).
3. Cache CalDAV leger pour accelerer lagenda en CLI.
4. Preferences utilisateur pour forcer le theme clair/sombre CustomTkinter.
5. Suite de tests (pytest) couvrant parsing Ollama et routage des calendriers.

## Support

- IRC : `#calendar-cli` sur irc.oftc.net
- Issues : <https://github.com/tobixen/plann/issues>

Merci de verifier vos dependances avant douvrir un ticket. Bonne organisation !
