#!/bin/bash
sites=(realtrator bamaqmaquinas)
for site in "${sites[@]}"; do
    echo "=========================================="
    echo "INICIANDO (recuperacao): $site  ($(date))"
    echo "=========================================="
    python scripts/sync_site.py --site "$site"
    echo "TERMINOU: $site  ($(date))"
done
echo "RECUPERACAO CONCLUIDA ($(date))"
