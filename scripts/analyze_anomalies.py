import json
from collections import Counter, defaultdict

def main():
    anomalies = []
    with open("logs/sim2real_anomalies.jsonl", "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    anomalies.append(json.loads(line))
                except Exception:
                    pass

    print(f"Total de anomalias registradas: {len(anomalies)}")
    
    types = Counter(a.get("anomaly_type") for a in anomalies)
    print("\n=== Por Tipo de Anomalia ===")
    for t, c in types.most_common():
        print(f"  {t}: {c} ({c/len(anomalies):.1%})")

    heroes = Counter(a.get("hero") for a in anomalies)
    print("\n=== Top 10 Heróis com Anomalias ===")
    for h, c in heroes.most_common(10):
        print(f"  {h}: {c}")

    phases = Counter(a.get("phase") for a in anomalies)
    print("\n=== Por Fase de Jogo ===")
    for p, c in phases.most_common(10):
        print(f"  {p}: {c}")

    diff_keys = Counter()
    diff_patterns = Counter()
    for a in anomalies:
        diffs = a.get("extra_context", {}).get("diffs", {})
        if isinstance(diffs, dict):
            pattern = []
            for k, v in diffs.items():
                diff_keys[k] += 1
                if isinstance(v, dict) and "expected" in v and "actual" in v:
                    pattern.append(f"{k}(exp={v['expected']},act={v['actual']})")
                else:
                    pattern.append(k)
            diff_patterns[", ".join(sorted(pattern))] += 1

    print("\n=== Chaves de Divergência Mais Frequentes ===")
    for k, c in diff_keys.most_common(10):
        print(f"  {k}: {c}")

    print("\n=== Padrões de Divergência Mais Frequentes ===")
    for pat, c in diff_patterns.most_common(10):
        print(f"  [{c}x] {pat}")

    # Exemplos representativos por padrão principal
    print("\n=== Amostras Detalhadas por Categoria ===")
    samples_by_type = defaultdict(list)
    for a in anomalies:
        samples_by_type[a.get("anomaly_type")].append(a)

    for atype, items in samples_by_type.items():
        print(f"\n--- Categoria: {atype} (Amostra de até 3 casos) ---")
        for ex in items[:3]:
            print(f"Hero: {ex.get('hero')} | Turn: {ex.get('turn')} | Phase: {ex.get('phase')} | Action: {ex.get('last_action')}")
            print(f"Message: {ex.get('message')}")
            diffs = ex.get('extra_context', {}).get('diffs')
            if diffs:
                print(f"Diffs: {diffs}")

if __name__ == "__main__":
    main()
