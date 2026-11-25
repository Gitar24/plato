#!/usr/bin/env bash
# Como usar: ./run.sh service | ./run.sh pet | ./run.sh autostart
# Roda sem Docker, com as variáveis do .env desta pasta. Equivalente Linux do run.ps1.
set -euo pipefail
root="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
py="$HOME/.local/venvs/plato/bin/python"
what="${1:-service}"

if [ -f "$root/.env" ]; then
    while IFS='=' read -r k v; do
        k="$(echo "$k" | xargs)"
        [[ -z "$k" || "$k" == \#* ]] && continue
        export "$k=$(echo "$v" | xargs)"
    done < <(grep -E '^\s*[^#[:space:]][^=]*=' "$root/.env")
fi

case "$what" in
    service)
        export CONFIG_PATH="$root/config/config.json" DATA_DIR="$root/data"
        export VAULT_PATH="${OBSIDIAN_VAULT_PATH:-}"
        cd "$root/service"
        exec "$py" -u app.py
        ;;
    pet)
        # No Wayland a janela não consegue se posicionar sozinha; o XWayland resolve.
        if [ "${XDG_SESSION_TYPE:-}" = "wayland" ] && [ -z "${QT_QPA_PLATFORM:-}" ]; then
            export QT_QPA_PLATFORM=xcb
        fi
        # grep sem -q lê tudo; com -q o ldconfig levaria SIGPIPE e o pipefail daria falso alarme
        libs="$(PATH="$PATH:/sbin:/usr/sbin" ldconfig -p 2>/dev/null || true)"
        if [ "${QT_QPA_PLATFORM:-xcb}" = "xcb" ] && [ -n "$libs" ] \
                && ! grep 'libxcb-cursor\.so\.0' <<< "$libs" > /dev/null; then
            echo "Falta uma biblioteca de que o Qt precisa. Instale com:" >&2
            echo "  sudo apt install libxcb-cursor0" >&2
            exit 1
        fi
        cd "$root/pet"
        exec "$py" main.py
        ;;
    autostart)
        # Abre o pet junto com a sessão (Mint/Cinnamon, GNOME, KDE, XFCE)
        dir="${XDG_CONFIG_HOME:-$HOME/.config}/autostart"
        mkdir -p "$dir"
        cat > "$dir/plato.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=Plato
Comment=Filósofo de pixel que comenta as notícias
Exec=$root/run.sh pet
Icon=$root/pet/assets/pet.png
Terminal=false
X-GNOME-Autostart-enabled=true
X-GNOME-Autostart-Delay=10
EOF
        echo "Pronto: $dir/plato.desktop. Para desfazer, apague esse arquivo."
        ;;
    *)
        echo "Uso: $0 service | pet | autostart" >&2
        exit 1
        ;;
esac
