#!/bin/bash
ROOM=TestMatch_live
echo "Iniciando: $ROOM"
rm -f logs/${ROOM}*.log logs/${ROOM}*.txt logs/${ROOM}*.json 2>/dev/null

./venv/bin/python bot_client.py --room $ROOM --deck decks/ira.json --role host --name Bot1 > /tmp/bot1.log 2>&1 &
PID1=$!
sleep 0.5
./venv/bin/python bot_client.py --room $ROOM --deck decks/rhinar.json --role join --name Bot2 > /tmp/bot2.log 2>&1 &
PID2=$!
echo "PIDs: $PID1 $PID2"
echo "Aguardando 3min..."

for i in $(seq 1 60); do
  sleep 5
  echo "--- t=${i}x5s ---"
  tail -4 logs/${ROOM}_Bot1_debug.log 2>/dev/null
  if grep -q "finalizou a partida" logs/${ROOM}_Bot1_debug.log 2>/dev/null || grep -q "Vencedor" logs/${ROOM}_summary.log 2>/dev/null; then
    echo "PARTIDA FINALIZADA COM SUCESSO!"
    break
  fi
done

echo "=== LOG COMPLETO BOT1 ==="
cat logs/${ROOM}_Bot1_debug.log 2>/dev/null

kill $PID1 $PID2 2>/dev/null
wait $PID1 $PID2 2>/dev/null
echo "=== FIM ==="
