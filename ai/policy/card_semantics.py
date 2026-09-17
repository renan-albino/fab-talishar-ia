"""
ai/policy/card_semantics.py
===========================
Motor de compreensão semântica genérica de cartas e contexto de arena para Flesh and Blood.
Interpreta atributos, palavras-chave canônicas, gatilhos de combate e efeitos contínuos/estáticos,
eliminando a necessidade de listas hardcoded nominais nas decisões de jogo.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any, Set
import os
import json
import re


@dataclass
class CardSemanticProfile:
    """Perfil semântico e funcional de uma carta de Flesh and Blood."""
    card_name: str
    card_type: str = "AA"
    subtype: str = ""
    keywords: List[str] = field(default_factory=list)
    evasion: Dict[str, Any] = field(default_factory=lambda: {
        "dominate": False,
        "overpower": False,
        "piercing": 0,
        "phantasm": False,
        "stealth": False,
    })
    extra_on_hit_damage: int = 0
    on_hit_disruption: Optional[str] = None
    on_hit_severity: float = 0.0
    grants_evasion: List[str] = field(default_factory=list)
    grants_piercing: int = 0
    arcane_threat: int = 0
    prevention: Dict[str, int] = field(default_factory=lambda: {
        "arcane_barrier": 0,
        "spellvoid": 0,
        "ward": 0,
        "quell": 0,
    })
    generates_ap: int = 0
    generates_resource: int = 0


@dataclass
class ArenaThreatContext:
    """Contexto holístico de ameaça e estado de combate derivado de todas as cartas na mesa."""
    chain_attack_name: str = ""
    chain_base_power: int = 0
    total_effective_physical_damage: int = 0
    extra_on_hit_damage: int = 0
    total_concurrent_arcane_damage: int = 0
    has_active_dominate: bool = False
    has_active_overpower: bool = False
    has_active_piercing: bool = False
    has_active_phantasm: bool = False
    composite_threat_score: float = 0.0
    is_lethal_danger: bool = False
    threat_reasons: List[str] = field(default_factory=list)
    opponent_prevention: Dict[str, int] = field(default_factory=lambda: {
        "arcane_barrier": 0,
        "spellvoid": 0,
        "ward": 0,
        "quell": 0,
    })


# ══════════════════════════════════════════════════════════════════
# CARREGAMENTO DE METADADOS SEMÂNTICOS CANÔNICOS (OFFLINE / CACHED)
# ══════════════════════════════════════════════════════════════════

_SEMANTICS_DB: Optional[Dict[str, Dict[str, Any]]] = None

def _load_semantics_db() -> Dict[str, Dict[str, Any]]:
    global _SEMANTICS_DB
    if _SEMANTICS_DB is None:
        base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
        db_path = os.path.join(base_dir, "data", "fab_card_semantics.json")
        if os.path.exists(db_path):
            try:
                with open(db_path, "r", encoding="utf-8") as f:
                    _SEMANTICS_DB = json.load(f)
            except Exception:
                _SEMANTICS_DB = {}
        else:
            _SEMANTICS_DB = {}
    return _SEMANTICS_DB


# ══════════════════════════════════════════════════════════════════
# PARSER SEMÂNTICO EM TEMPO REAL (DYNAMIC / RUNTIME FALLBACK)
# ══════════════════════════════════════════════════════════════════

def parse_card_semantics(card_name: str, card_data: Optional[Dict[str, Any]] = None) -> CardSemanticProfile:
    """
    Retorna o perfil semântico de uma carta consultando a base canônica
    ou aplicando regras semânticas dinâmicas de FaB por inferência textual.
    """
    c_clean = str(card_name or "").lower().strip()
    card_data = card_data or {}
    db = _load_semantics_db()

    # 1. Consulta ao banco de semântica pré-indexado
    if c_clean in db:
        cached = db[c_clean]
        return CardSemanticProfile(
            card_name=c_clean,
            card_type=cached.get("type", card_data.get("type", "AA")),
            subtype=cached.get("subtype", card_data.get("subtype", "")),
            keywords=cached.get("keywords", []),
            evasion=cached.get("evasion", {
                "dominate": False, "overpower": False, "piercing": 0, "phantasm": False, "stealth": False
            }),
            extra_on_hit_damage=int(cached.get("extra_on_hit_damage", 0)),
            on_hit_disruption=cached.get("on_hit_disruption"),
            on_hit_severity=float(cached.get("on_hit_severity", 0.0)),
            grants_evasion=cached.get("grants_evasion", []),
            grants_piercing=int(cached.get("grants_piercing", 0)),
            arcane_threat=int(cached.get("arcane_threat", 0)),
            prevention=cached.get("prevention", {
                "arcane_barrier": 0, "spellvoid": 0, "ward": 0, "quell": 0
            }),
            generates_ap=int(cached.get("generates_ap", 0)),
            generates_resource=int(cached.get("generates_resource", 0)),
        )

    # 2. Avaliador dinâmico de regras em tempo real (Runtime Fallback)
    text = str(card_data.get("text", "")).lower()
    c_type = str(card_data.get("type", "AA")).upper()
    c_subtype = str(card_data.get("subtype", "")).lower()
    keywords = [str(k).lower() for k in card_data.get("keywords", [])]

    evasion = {
        "dominate": "dominate" in keywords or "dominate" in text or "dominate" in c_clean,
        "overpower": "overpower" in keywords or "overpower" in text,
        "piercing": 1 if ("piercing" in keywords or "piercing" in text) else 0,
        "phantasm": "phantasm" in keywords or "phantasm" in text or "phantasm" in c_clean,
        "stealth": "stealth" in keywords or "stealth" in text,
    }

    # Dano extra On-Hit (ex: Boom Grenade, Mauling Qi, etc.)
    extra_damage = 0
    if "boom_grenade" in c_clean:
        extra_damage = 4 if "_red" in c_clean else (3 if "_yellow" in c_clean else 2)
    elif "mauling_qi" in c_clean:
        extra_damage = 1
    else:
        m_dmg = re.search(r"when (?:an?|this).*?hits.*?deal (\d+) damage", text)
        if m_dmg:
            extra_damage = int(m_dmg.group(1))

    # Categoria de disrupção On-Hit e severidade
    disruption = None
    severity = 0.0

    if any(k in c_clean for k in ["command_and_conquer", "leave_no_witnesses", "wreck_havoc", "eradicate"]) or ("destroy" in text and "arsenal" in text):
        disruption = "destroy_arsenal"
        severity = 10.0
    elif any(k in c_clean for k in ["crippling_crush", "surgical_extraction", "pummel"]) or ("discard" in text and "hand" in text):
        disruption = "discard_hand"
        severity = 7.5
    elif any(k in c_clean for k in ["red_in_the_ledger", "spinal_crush", "hypothermia"]) or ("can't" in text and "action" in text):
        disruption = "turn_lock"
        severity = 9.0
    elif any(k in c_clean or k in text for k in ["bloodrot", "frailty", "inertia"]):
        disruption = "affliction"
        severity = 4.0
    elif any(k in c_clean for k in ["snatch", "mask_of_momentum", "erudition"]) or ("draw" in text and ("hit" in text or "damage" in text)):
        disruption = "draw_cards"
        severity = 6.0
    elif extra_damage > 0:
        severity = min(10.0, float(extra_damage) * 1.5)

    # Itens que concedem modificadores a outros ataques
    grants_evasion = []
    if "convection_amplifier" in c_clean or ("convection" in text and "dominate" in text):
        grants_evasion.append("dominate")
    grants_piercing = 1 if ("penetration_script" in c_clean or "penetration" in text) else 0

    arcane_threat = 1 if ("runechant" in c_clean or "runechant" in text) else 0

    prevention = {
        "arcane_barrier": 1 if ("arcane barrier" in text or "nullrune" in c_clean) else 0,
        "spellvoid": 1 if ("spellvoid" in text or "spellvoid" in c_clean) else 0,
        "ward": 4 if "ward 4" in text else (1 if "ward" in text else 0),
        "quell": 1 if "quell" in text else 0,
    }

    return CardSemanticProfile(
        card_name=c_clean,
        card_type=c_type,
        subtype=c_subtype,
        keywords=keywords,
        evasion=evasion,
        extra_on_hit_damage=extra_damage,
        on_hit_disruption=disruption,
        on_hit_severity=severity,
        grants_evasion=grants_evasion,
        grants_piercing=grants_piercing,
        arcane_threat=arcane_threat,
        prevention=prevention,
        generates_ap=1 if "crank" in keywords or "crank" in text else 0,
        generates_resource=2 if "teklo_core" in c_clean else 0,
    )


# ══════════════════════════════════════════════════════════════════
# SÍNTESE DO CONTEXTO DE AMEAÇA DA ARENA (ARENA THREAT EVALUATOR)
# ══════════════════════════════════════════════════════════════════

def build_arena_threat_context(state: dict, my_hp: Optional[int] = None) -> ArenaThreatContext:
    """
    Varre o elo de ataque ativo e todas as coleções de itens, auras,
    permanentes e equipamentos do oponente na arena para formular um
    diagnóstico holístico e quantitativo da ameaça de combate.
    """
    if not isinstance(state, dict):
        return ArenaThreatContext()

    if my_hp is None:
        my_hp = int(state.get("playerHealth", 20))

    active_chain = state.get("activeChainLink", {})
    if not isinstance(active_chain, dict):
        active_chain = {}

    chain_card_name = str(active_chain.get("cardNumber", "")).lower()
    base_power = int(active_chain.get("totalPower", state.get("combatChainPower", 0)))
    chain_type = str(active_chain.get("type", "AA")).upper()

    attack_profile = parse_card_semantics(chain_card_name, active_chain)

    has_dominate = bool(
        attack_profile.evasion.get("dominate")
        or active_chain.get("dominate")
        or active_chain.get("hasDominate")
        or state.get("dominate")
    )
    has_overpower = bool(
        attack_profile.evasion.get("overpower")
        or active_chain.get("overpower")
        or active_chain.get("hasOverpower")
        or state.get("overpower")
    )
    has_piercing = bool(
        attack_profile.evasion.get("piercing", 0) > 0
        or active_chain.get("piercing")
        or active_chain.get("hasPiercing")
        or state.get("piercing")
    )
    has_phantasm = bool(
        attack_profile.evasion.get("phantasm")
        or active_chain.get("phantasm")
        or active_chain.get("hasPhantasm")
        or state.get("phantasm")
    )

    extra_on_hit = attack_profile.extra_on_hit_damage
    composite_threat = attack_profile.on_hit_severity
    threat_reasons: List[str] = []

    if attack_profile.on_hit_disruption:
        threat_reasons.append(f"Ataque com On-Hit: {attack_profile.on_hit_disruption} (Severidade {attack_profile.on_hit_severity})")

    # ── 1. Inspecionar Itens do Oponente na Arena (opponentItems / theirItems) ──
    opp_items = state.get("opponentItems") or state.get("theirItems") or []
    for item in opp_items:
        if not isinstance(item, dict):
            continue
        i_name = str(item.get("cardNumber", item.get("name", ""))).lower()
        i_counters = int(item.get("counters", item.get("steam_counters", 1)))
        i_profile = parse_card_semantics(i_name, item)

        # Itens que aumentam dano On-Hit condicional (ex: Boom Grenade)
        if i_profile.extra_on_hit_damage > 0:
            # Dispara se o ataque for de ação (AA)
            if chain_type in ("AA", "ATTACK", ""):
                extra_on_hit += i_profile.extra_on_hit_damage
                composite_threat += float(i_profile.extra_on_hit_damage) * 1.5
                threat_reasons.append(f"Item na Arena: {i_name} (+{i_profile.extra_on_hit_damage} dano no acerto)")

        # Itens que concedem Evasão (ex: Convection Amplifier concedendo Dominate)
        if "dominate" in i_profile.grants_evasion and i_counters > 0:
            has_dominate = True
            threat_reasons.append(f"Item na Arena: {i_name} (Concede Dominate)")

        # Itens que concedem Piercing (ex: Penetration Script)
        if i_profile.grants_piercing > 0 and i_counters > 0:
            has_piercing = True
            threat_reasons.append(f"Item na Arena: {i_name} (Concede Piercing {i_profile.grants_piercing})")

    # ── 2. Inspecionar Auras e Fichas do Oponente (opponentAuras / theirAuras) ──
    opp_auras = (state.get("opponentAuras") or state.get("theirAuras") or []) + (state.get("opponentTokens") or state.get("theirTokens") or [])
    concurrent_arcane = 0
    for aura in opp_auras:
        if not isinstance(aura, dict):
            continue
        a_name = str(aura.get("cardNumber", aura.get("name", ""))).lower()
        a_profile = parse_card_semantics(a_name, aura)
        a_count = max(1, int(aura.get("counters", aura.get("count", 1))))

        if a_profile.arcane_threat > 0 or "runechant" in a_name:
            concurrent_arcane += a_count
            threat_reasons.append(f"Aura na Arena: {a_count}x Runechants ({a_count} Dano Arcano concorrente)")
        elif "might" in a_name:
            threat_reasons.append("Aura na Arena: Might (+1 poder no ataque)")

    # ── 3. Inspecionar Prevenções do Oponente (Ward, Spellvoid, Arcane Barrier) ─
    opp_prevention = {"arcane_barrier": 0, "spellvoid": 0, "ward": 0, "quell": 0}
    opp_permanents = (state.get("opponentPermanents") or state.get("theirPermanents") or []) + (state.get("opponentEquipment") or state.get("theirEquipment") or [])
    for perm in opp_permanents:
        if not isinstance(perm, dict):
            continue
        p_name = str(perm.get("cardNumber", perm.get("name", ""))).lower()
        p_profile = parse_card_semantics(p_name, perm)
        for prev_key, prev_val in p_profile.prevention.items():
            opp_prevention[prev_key] += prev_val

    total_physical = base_power + extra_on_hit
    total_potential_damage = total_physical + concurrent_arcane
    is_lethal = bool(my_hp <= total_potential_damage)

    if is_lethal:
        threat_reasons.append(f"PERIGO LETAL: Dano Potencial {total_potential_damage} >= Vida Atual {my_hp}")

    return ArenaThreatContext(
        chain_attack_name=chain_card_name,
        chain_base_power=base_power,
        total_effective_physical_damage=total_physical,
        extra_on_hit_damage=extra_on_hit,
        total_concurrent_arcane_damage=concurrent_arcane,
        has_active_dominate=has_dominate,
        has_active_overpower=has_overpower,
        has_active_piercing=has_piercing,
        has_active_phantasm=has_phantasm,
        composite_threat_score=composite_threat,
        is_lethal_danger=is_lethal,
        threat_reasons=threat_reasons,
        opponent_prevention=opp_prevention,
    )
