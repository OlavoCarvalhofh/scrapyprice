#!/bin/bash
sites=(tratormag jerdrones)
for site in "${sites[@]}"; do
    echo "=========================================="
    echo "INICIANDO (recuperacao DNS): $site  ($(date))"
    echo "=========================================="
    python scripts/sync_site.py --site "$site"
    echo "TERMINOU: $site  ($(date))"
done
echo "RECUPERACAO DNS CONCLUIDA ($(date))"
