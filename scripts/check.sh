#!/bin/sh
# Quick diagnostics. Run from the endstone-test/ folder:  sh scripts/check.sh
echo "== Backend: version and xuidforward lines =="
docker logs endstone-test 2>&1 | grep -iE "version|xuidforward|profile|signature|hook" | tail -25
echo
echo "== Backend: effective server.properties =="
docker exec endstone-test sh -c 'f=$(find /data -maxdepth 4 -name server.properties -not -path "*/worlds/*" | head -1); echo "$f"; grep -E "^(server-ip|server-port|server-udp-ports|transport|online-mode|allow-list|enable-lan-visibility|level-name)=" "$f"'
echo
echo "== Backend: recent logins (look at the xuid: value) =="
docker logs endstone-test 2>&1 | grep -iE "connected|spawned|disconnected" | tail -10
echo
echo "== Waterdog =="
docker logs bds-test-waterdog 2>&1 | grep -iE "registered|xuid|error|warn" | tail -10