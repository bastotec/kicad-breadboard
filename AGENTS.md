# Project agent memory

This file is the project's committed home for project-intrinsic agent knowledge: build, test, release, architecture, and sharp-edge notes that should travel with the code.

- Run `python3 -m unittest discover -s tests -v` for regression tests; the UI suite requires wxPython and a supported display and otherwise reports a skip.
- Use `python3 -m plugins.breadboard.standalone` for development without installing the plugin. The main wx layout is in `plugins/breadboard/window.py`; canvas selection lives in `plugins/breadboard/canvas.py`.
- Renderer templates in `plugins/breadboard/model/components.py` are heuristic layouts, not verified manufacturer identities. Session compatibility is owned by `plugins/breadboard/model/session.py`.

## Public verification artifacts

Use synthetic generic circuits only. Mechanically scan the final rendered PR body
and every attachment, as well as the diff, fixtures and supplied intent, for
private names, workstation paths and internal run identifiers before publishing.
Keep diagnostic logs private. Evidence drivers intended for publication must use
relative or caller-supplied output paths, never hard-coded local evidence paths
or run identifiers. Do not attach unsanitized diagnostic scripts or session files.
Use an existing supported runtime for verification; do not install dependencies
or activate a separate desktop installation as part of this change.

## Maintaining this file

Keep this file for knowledge useful to almost every future agent session in this project.
Do not repeat what the codebase already shows; point to the authoritative file or command instead.
Prefer rewriting or pruning existing entries over appending new ones.
When updating this file, preserve this bar for all agents and keep entries concise.
