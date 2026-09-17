"""
ai/policy/engine.py
===================
PolicyEngine: Motor de Decisão Híbrido com Poda Tática Baseada em Regras de Flesh and Blood.
"""

import os
import torch
from typing import Dict, List, Optional, Tuple, Any


from ..model import FaBPolicyValueNetwork, create_model, get_device
from ..mcts import MCTSEngine, ISMCTSEngine
from ..ismcts_logger import ISMCTSLogger

from .card_evaluator import (
    extract_card_info,
    calculate_available_resources,
    get_weapon_cost,
    get_all_known_zone_cards,
)
from .attack_pruner import select_best_attack
from .defense_pruner import select_defense_blocks
from .pitch_pruner import select_best_pitch_card
from .arsenal_pruner import select_arsenal_card


class PolicyEngine:
    """Motor de Decisão Híbrido (ISMCTS / MCTS + Rede Neural Policy-Value + Heurísticas de FaB)."""

    def __init__(
        self,
        hero_name: str = "generic",
        model_path: str = None,
        use_gpu: bool = True,
        num_mcts_sims: int = None,
        room_id: str = "unknown",
    ):
        self.hero_name = hero_name
        from ..hero_strategies import get_hero_strategy
        self.strategy: Any = get_hero_strategy(hero_name)
        self.room_id = room_id

        try:
            from config.settings import SETTINGS
            default_model_path = SETTINGS.teacher_checkpoint
            default_mcts_sims = SETTINGS.mcts_simulations
            default_device = torch.device(SETTINGS.device if use_gpu else "cpu")
        except Exception:
            default_model_path = "data/checkpoints/teacher_latest.pt"
            default_mcts_sims = 25
            default_device = get_device() if use_gpu else torch.device("cpu")

        self.num_mcts_sims = num_mcts_sims if num_mcts_sims is not None else default_mcts_sims
        self.device = default_device
        self.model = None

        target_path = model_path or default_model_path
        if target_path and os.path.exists(target_path):
            try:
                self.model, _ = create_model(target_path, str(self.device))
            except Exception as e:
                print(f"[PolicyEngine] Aviso ao inicializar modelo PyTorch: {e}")

        # Motor MCTS clássico (para estados com informação completa ou fallback)
        self.mcts = MCTSEngine(
            model=self.model,
            device=str(self.device),
            single_player_tree=True,
        )

        # Motor ISMCTS (para estados com mão oculta do oponente)
        self.ismcts = ISMCTSEngine(
            model=self.model,
            device=str(self.device),
        )

        # Logger de decisões ISMCTS
        self.ismcts_logger = ISMCTSLogger(
            room_id=self.room_id,
            hero=self.hero_name,
        )

    def set_model(self, model: FaBPolicyValueNetwork, device: torch.device = None):
        """Atualiza a rede neural de política e valor e reinstancia motores MCTS."""
        self.model = model
        if device:
            self.device = device
        self.mcts = MCTSEngine(
            model=self.model,
            device=str(self.device),
            single_player_tree=True,
        )
        self.ismcts = ISMCTSEngine(
            model=self.model,
            device=str(self.device),
        )

    def update_room_id(self, room_id: str, hero_name: str = None) -> None:
        """Atualiza room_id e hero do logger (chamado após o sideboard)."""
        self.room_id = room_id
        if hero_name:
            self.hero_name = hero_name
            from ..hero_strategies import get_hero_strategy
            self.strategy = get_hero_strategy(hero_name)
        self.ismcts_logger = ISMCTSLogger(
            room_id=self.room_id,
            hero=self.hero_name,
        )

    def get_weapon_cost(self, weapon_name: str, equip_dict: dict = None, state: dict = None, eq: dict = None) -> int:
        """Retorna o custo em recursos para ativar a arma ou habilidade de equipamento."""
        target_eq = eq if eq is not None else equip_dict
        return get_weapon_cost(
            weapon_name,
            eq=target_eq,
            state=state,
            hero_name=self.hero_name,
            strategy=self.strategy,
        )

    @staticmethod
    def get_all_known_zone_cards(state: dict) -> Dict[str, List[dict]]:
        """Retorna um mapa consolidado de todas as cartas em todas as zonas do jogo."""
        return get_all_known_zone_cards(state)

    def extract_card_info(self, card: dict) -> dict:
        """Extrai e normaliza atributos de cartas a partir do snapshot e banco de dados."""
        return extract_card_info(card)

    def calculate_available_resources(self, state: dict) -> Tuple[int, int]:
        """Calcula recursos flutuantes atuais e potencial total de pitch da mão."""
        return calculate_available_resources(state)

    def is_teklovossen_ability_active(self, state: dict) -> bool:
        """
        Regra oficial FaB: Evos do Banish só ganham a opção de serem jogados como Instant
        se a habilidade de Teklovossen ({r}{r}: Bane Evo da mão, compra carta) tiver sido ativada no turno.
        Delega polimorficamente para self.strategy.is_hero_ability_active(state).
        """
        return self.strategy.is_hero_ability_active(state)

    def select_best_attack(self, state: dict, unpayable_set: Optional[set] = None) -> Optional[Dict[str, Any]]:
        """Seleciona o melhor candidato de ataque coordenando podas e busca ISMCTS/MCTS."""
        return select_best_attack(self, state, unpayable_set=unpayable_set)

    def select_defense_blocks(self, state: dict) -> List[Tuple[int, str, str, int]]:
        """Seleciona a melhor combinação de bloqueadores otimizando breakpoints e preservando contra-ataque."""
        return select_defense_blocks(self, state)

    def select_best_pitch_card(self, state: dict, target_cost: int = 1) -> Optional[Tuple[int, str, int]]:
        """Delega a escolha de pitch para o pruner especializado."""
        return select_best_pitch_card(self, state, target_cost)

    def select_arsenal_card(self, state: dict) -> Optional[Tuple[str, str]]:
        """Seleciona a melhor carta para o Arsenal respeitando a proibição de pitch e modo cavar."""
        return select_arsenal_card(self, state)
