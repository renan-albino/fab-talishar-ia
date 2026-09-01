import subprocess
import json
import os

php_code = """<?php
include "/var/www/html/game/GeneratedCode/GeneratedCardDictionaries.php";
$file = file_get_contents("/var/www/html/game/GeneratedCode/GeneratedCardDictionaries.php");
preg_match_all('/"([a-zA-Z0-9_]+)" =>/', $file, $matches);
$cardIDs = array_unique($matches[1]);
$db = [];
foreach ($cardIDs as $id) {
    $t = GeneratedCardType($id);
    $st = GeneratedCardSubtype($id);
    $name = GeneratedCardName($id);
    $is1h = GeneratedIs1H($id);
    $class = GeneratedCardClass($id);
    $slot = "Deck";
    if ($t === "C") $slot = "Hero";
    elseif ($t === "W") $slot = "Weapon";
    elseif ($t === "E") {
        if (strpos($st, "Head") !== false) $slot = "Head";
        elseif (strpos($st, "Chest") !== false) $slot = "Chest";
        elseif (strpos($st, "Arms") !== false) $slot = "Arms";
        elseif (strpos($st, "Legs") !== false) $slot = "Legs";
        elseif (strpos($st, "Off-Hand") !== false || strpos($st, "Quiver") !== false || strpos($st, "Companion") !== false) $slot = "Off-Hand";
        else $slot = "Equipment";
    }
    $db[$id] = [
        "id" => $id,
        "name" => $name,
        "type" => $t,
        "subtype" => $st,
        "slot" => $slot,
        "is1h" => $is1h,
        "class" => $class
    ];
}
echo json_encode($db);
"""

print("Extracting card database from Talishar Docker...")
res = subprocess.run(
    ["docker", "exec", "-i", "talishar-web-server-1", "php"],
    input=php_code.encode("utf-8"),
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE
)

if res.returncode == 0:
    data = json.loads(res.stdout.decode("utf-8"))
    os.makedirs("data", exist_ok=True)
    with open("data/fab_cards_db.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Sucesso! {len(data)} cartas catalogadas em data/fab_cards_db.json")
else:
    print("❌ Erro:", res.stderr.decode("utf-8"))
