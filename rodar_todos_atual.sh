#!/bin/bash
sites=(agrotrator fornecedoramaquinas fornecedoraagro carpaltratores pitstop acamargo superagrosc tratormag jerdrones goldrones prosperadistribuicao newpecasoficial agripecas premierdrones geotrackconsultoria worldwidebrasil dronedireto agroshopbr lojaododrone paccini fontanatratorpecas dronesense tratorlin realtrator bamaqmaquinas)
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
