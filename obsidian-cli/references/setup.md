# Obsidian CLI Setup

## Requirements

- Obsidian installer version **1.12.7 or later**
- To check: Obsidian → Help → About → look for "Installer version"
- If older: download the latest installer from https://obsidian.md

## Enable the CLI

1. Open Obsidian
2. Go to **Settings** → **General**
3. Toggle on **Command line interface**
4. Follow the prompt to register the CLI (adds `obsidian` to your system PATH)
5. **Restart your terminal** — PATH changes only take effect in new sessions

## Verify Installation

```bash
obsidian version
# Expected output: a version number, e.g. 1.12.7
```

## Platform Notes

### Linux

The CLI binary is copied to `~/.local/bin/obsidian`. Ensure this is in your PATH:

```bash
# Check
echo $PATH | grep -q "$HOME/.local/bin" && echo "OK" || echo "Missing"

# Add to PATH if missing — add this line to ~/.bashrc or ~/.zshrc:
export PATH="$PATH:$HOME/.local/bin"
```

### macOS

A symlink is created at `/usr/local/bin/obsidian`. Requires admin privileges (a system dialog appears during registration).

```bash
# Verify symlink
ls -l /usr/local/bin/obsidian

# If missing, create manually:
sudo ln -sf /Applications/Obsidian.app/Contents/MacOS/obsidian-cli /usr/local/bin/obsidian
```

### Windows

The Obsidian installer directory is added to your user PATH. Restart the terminal after registration. Requires Obsidian 1.12.7+ installer.

## Troubleshooting

| Symptom | Fix |
|---|---|
| `obsidian: command not found` | Restart terminal; check PATH for your platform |
| `No vault` error | Open Obsidian and ensure a vault is active |
| Commands hang | Obsidian app may not be running — launch it first |
| Old PATH entry in `~/.zprofile` | Delete lines starting with `# Added by Obsidian` (replaced by new registration) |
