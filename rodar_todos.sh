#!/bin/bash
sites=(agrotrator fornecedoramaquinas fornecedoraagro carpaltratores pitstop tratorlin acamargo superagrosc tratormag jerdrones prosperadistribuicao newpecasoficial engepecas paccini)
for site in "${sites[@]}"; do
    echo "=========================================="
    echo "INICIANDO: $site  ($(date))"
    echo "=========================================="
    python scripts/sync_site.py --site "$site"
    echo "TERMINOU: $site  ($(date))"
done
echo "=========================================="
echo "TODOS OS SITES CONCLUIDOS ($(date))"
echo "=========================================="
