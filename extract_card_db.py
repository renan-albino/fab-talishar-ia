import subprocess
import json
import os
import sys

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

def extract_from_local():
    local_path = os.path.join(os.path.dirname(__file__), "Talishar", "GeneratedCode", "GeneratedCardDictionaries.php")
    if not os.path.exists(local_path):
        return None
    import re
    print(f"Lendo dicionários diretamente de {local_path}...")
    with open(local_path, "r", encoding="utf-8") as f:
        php = f.read()

    def parse_match(func_name, end_func_name):
        start = php.find(f"function {func_name}")
        if start == -1: return {}
        end = php.find(f"function {end_func_name}", start) if end_func_name else len(php)
        section = php[start:end]
        res = {}
        for k, v in re.findall(r'"([a-zA-Z0-9_]+)"\s*=>\s*(-?\d+|"[^"]*"|true|false)', section):
            if v == "true": res[k] = True
            elif v == "false": res[k] = False
            else:
                try: res[k] = int(v)
                except ValueError: res[k] = v.strip('"')
        return res

    costs = parse_match("GeneratedCardCost($cardID)", "GeneratedCardSubtype($cardID)")
    powers = parse_match("GeneratedPowerValue($cardID)", "GeneratedBlockValue($cardID)")
    blocks = parse_match("GeneratedBlockValue($cardID)", "GeneratedCardName($cardID)")
    pitches = parse_match("GeneratedPitchValue($cardID)", "GeneratedCardCost($cardID)")
    go_agains = parse_match("GeneratedGoAgain($cardID)", "GeneratedHasAmbush($cardID)")
    types = parse_match("GeneratedCardType($cardID)", "GeneratedPowerValue($cardID)")
    subtypes = parse_match("GeneratedCardSubtype($cardID)", "GeneratedCharacterHealth($cardID)")
    names = parse_match("GeneratedCardName($cardID)", "GeneratedPitchValue($cardID)")
    classes = parse_match("GeneratedCardClass($cardID)", "GeneratedCardTalent($cardID)")
    is1hs = parse_match("GeneratedIs1H($cardID)", "GeneratedCardClass($cardID)")

    all_ids = set(types.keys()) | set(names.keys()) | set(costs.keys())
    db = {}
    for cid in all_ids:
        t = types.get(cid, "AA")
        st = subtypes.get(cid, "")
        slot = "Deck"
        if t == "C": slot = "Hero"
        elif t == "W": slot = "Weapon"
        elif t == "E":
            if "Head" in st: slot = "Head"
            elif "Chest" in st: slot = "Chest"
            elif "Arms" in st: slot = "Arms"
            elif "Legs" in st: slot = "Legs"
            elif "Off-Hand" in st or "Quiver" in st or "Companion" in st: slot = "Off-Hand"
            else: slot = "Equipment"

        cost_val = costs.get(cid, 0 if t in ("AA", "A", "AR", "DR", "I", "NA") else 0)
        if isinstance(cost_val, int) and cost_val < 0: cost_val = 0

        card_data = {
            "id": cid,
            "name": names.get(cid, cid.replace("_", " ").title()),
            "type": t,
            "subtype": st,
            "slot": slot,
            "is1h": bool(is1hs.get(cid, False)),
            "class": classes.get(cid, "GENERIC"),
            "cost": cost_val,
        }
        if cid in powers and powers[cid] >= 0:
            card_data["power"] = powers[cid]
        if cid in blocks and blocks[cid] >= 0:
            card_data["defense"] = blocks[cid]
        if cid in pitches and pitches[cid] >= 0:
            card_data["pitch"] = pitches[cid]
        if cid in go_agains:
            card_data["has_go_again"] = bool(go_agains[cid])
        db[cid] = card_data
    return db

data = extract_from_local()
if data:
    os.makedirs("data", exist_ok=True)
    with open("data/fab_cards_db.json", "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)
    print(f"✅ Sucesso local! {len(data)} cartas catalogadas em data/fab_cards_db.json")
    sys.exit(0)

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
    sys.exit(1)
