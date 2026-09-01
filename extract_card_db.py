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

def get_web_container():
    # 1. Search running containers with web-server in name
    try:
        res = subprocess.check_output(["docker", "ps", "--filter", "name=web-server", "--format", "{{.Names}}"], text=True)
        containers = [c.strip() for c in res.strip().splitlines() if c.strip()]
        if containers:
            return containers[0]
    except Exception:
        pass

    # 2. Test common container names
    for cand in ["talishar_web-server_1", "talishar-web-server-1", "talishar-web-server", "web-server"]:
        try:
            r = subprocess.run(["docker", "inspect", cand], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            if r.returncode == 0:
                return cand
        except Exception:
            pass

    # 3. Search any running container related to talishar
    try:
        res = subprocess.check_output(["docker", "ps", "--format", "{{.Names}}"], text=True)
        for n in res.strip().splitlines():
            name = n.strip()
            if ("talishar" in name.lower() or "web" in name.lower()) and not any(x in name.lower() for x in ["mysql", "redis", "admin"]):
                return name
    except Exception:
        pass

    return "talishar_web-server_1"

container_name = get_web_container()
print(f"Extracting card database from Talishar Docker (container: {container_name})...")
res = subprocess.run(
    ["docker", "exec", "-i", container_name, "php"],
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
    err = res.stderr.decode("utf-8")
    print("❌ Erro:", err)
    # Don't fail silently if container not running or failed
    sys.exit(1)
