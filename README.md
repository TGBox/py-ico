# py-ico

A small python app to generate .ico files from image input.

## Tech-Stack

- **Sprache:** Python
- **Build / Packaging:** uv
- **CI/CD:** GitHub Actions
## Ordnerstruktur

```text
py-ico/
├── src/
│   ├── __init__.py
│   ├── main.py
│   ├── build.py
│   └── tools.py
├── tests/
│   └── test_main.py
├── .github/workflows/ci.yml├── .gitignore
├── pyproject.toml
└── README.md
```

## Quickstart

```bash
git clone <repo-url>
cd py-ico
uv sync

# App ausführen
uv run main
# oder:
uv run py-ico

# Tests ausführen
uv run test

# Exe-Datei mit PyInstaller erstellen
uv run build
```