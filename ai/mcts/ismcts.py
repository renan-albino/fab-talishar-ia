"""
ai/mcts/ismcts.py
=================
ISMCTSEngine: Information Set MCTS para jogos de informação imperfeita (Flesh and Blood).

Estratégia:
  1. Gera W mundos determinizados preenchendo a mão oculta do oponente.
  2. Em cada mundo, roda MCTSEngine com batch leaf evaluation.
  3. Agrega votos: a ação com maior total de visit_counts entre mundos é escolhida.

Número de mundos: calculado em startup via hardware scan (_probe_inference_latency_ms)
e armazenado em SETTINGS.ismcts_worlds — proporcional à latência real medida.

Referência: Cowling, Powley & Whitehouse (2012), IEEE Transactions on Games.
"""

import os
import multiprocessing as mp
import concurrent.futures
import numpy as np
from typing import Dict, Any, List, Optional, Tuple

from ai.model import FaBPolicyValueNetwork
from ai.logger import get_logger
from .node import MCTSNode
from .standard_mcts import MCTSEngine, _get_c_puct
from .world_generator import generate_worlds
from .inference_server import BatchedInferenceServer, RemoteModelProxy

logger = get_logger("mcts")


def _get_ismcts_worlds() -> int:
    """Retorna número de mundos ISMCTS calculado por hardware scan no startup."""
    try:
        from config.settings import SETTINGS
        return SETTINGS.ismcts_worlds
    except Exception as e:
        logger.warning(f"Erro em _get_ismcts_worlds: {e}. Usando fallback 4.")
        return 4


def _extract_level1_summary(
    root: MCTSNode,
    best_idx: int,
    world_idx: int,
) -> Dict[str, Any]:
    """
    Extrai o resumo de Nível 1 (Escolha C):
    Estatísticas da Raiz e de seus Filhos Diretos (ações imediatas).
    Payload leve e eficiente para IPC entre processos.
    """
    children_stats: Dict[int, Dict[str, Any]] = {}
    for act_idx, child in root.children.items():
        if act_idx >= 0:
            children_stats[act_idx] = {
                "action_id": child.action_id,
                "action_name": child.action_name,
                "visit_count": child.visit_count,
                "value_sum": float(child.value_sum),
                "q_value": float(child.q_value),
                "prior": float(child.prior),
            }

    return {
        "world_idx": world_idx,
        "best_idx": best_idx,
        "root_stats": {
            "visit_count": root.visit_count,
            "value_sum": float(root.value_sum),
            "q_value": float(root.q_value),
        },
        "children_stats": children_stats,
    }


def _ismcts_worker_process(
    conn,
    world_idx: int,
    world_state: Dict[str, Any],
    legal_actions: List[Dict[str, Any]],
    num_simulations: int,
    training_mode: bool,
    c_puct: float,
    state_vec: np.ndarray,
) -> None:
    """
    Função de execução do Worker (Actor) em processo isolado.
    Utiliza RemoteModelProxy para delegar inferência ao processo principal via Pipe.
    Garante isolamento completo da GPU/CUDA no worker.
    """
    os.environ["CUDA_VISIBLE_DEVICES"] = ""

    try:
        proxy = RemoteModelProxy(conn)
        mcts = MCTSEngine(
            model=proxy,
            device="cpu",
            c_puct=c_puct,
            single_player_tree=True,
        )

        num_legal = len(legal_actions)
        if num_legal == 0:
            conn.send(("done", {
                "world_idx": world_idx,
                "best_idx": 0,
                "root_stats": {},
                "children_stats": {},
            }))
            return

        priors, base_value = mcts._evaluate(state_vec)

        root = MCTSNode(prior=1.0)
        mcts._expand(root, legal_actions, priors)

        if training_mode and root.children:
            mcts._add_dirichlet_noise(root, len(root.children) + len(root.pending))

        leaf_nodes: List[MCTSNode] = []
        for sim_idx in range(num_simulations):
            mcts._progressive_widen(root, sim_idx)
            node = mcts._select(root)
            leaf_nodes.append(node)

        leaf_values = mcts._batch_evaluate_leaves(
            root_state_vec=state_vec,
            nodes=leaf_nodes,
            base_value=base_value,
            state=world_state,
            legal_actions=legal_actions,
            world_seed=world_idx,
        )

        for node, lv in zip(leaf_nodes, leaf_values):
            mcts._backpropagate(node, lv)

        best_idx = mcts._select_action(root, legal_actions, training_mode)
        summary = _extract_level1_summary(root, best_idx, world_idx)
        conn.send(("done", summary))

    except Exception as e:
        logger.error(f"Erro no worker ISMCTS mundo {world_idx}: {e}", exc_info=True)
        try:
            conn.send(("done", {
                "world_idx": world_idx,
                "best_idx": 0,
                "root_stats": {},
                "children_stats": {},
                "error": str(e),
            }))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


def _ismcts_direct_gpu_worker_process(
    conn,
    world_idx: int,
    world_state: Dict[str, Any],
    legal_actions: List[Dict[str, Any]],
    num_simulations: int,
    training_mode: bool,
    c_puct: float,
    state_vec: np.ndarray,
    device: str,
    model: Optional[Any] = None,
) -> None:
    """
    Função de execução do Worker direct_gpu em processo isolado.
    Executa a inferência MCTS diretamente na GPU sem IPC com o processo pai.
    """
    try:
        if model is not None:
            try:
                if hasattr(model, "to"):
                    model = model.to(device)
                if hasattr(model, "eval"):
                    model.eval()
            except Exception:
                pass

        mcts = MCTSEngine(
            model=model,
            device=device,
            c_puct=c_puct,
            single_player_tree=True,
        )

        num_legal = len(legal_actions)
        if num_legal == 0:
            conn.send(("done", {
                "world_idx": world_idx,
                "best_idx": 0,
                "root_stats": {},
                "children_stats": {},
            }))
            return

        priors, base_value = mcts._evaluate(state_vec)

        root = MCTSNode(prior=1.0)
        mcts._expand(root, legal_actions, priors)

        if training_mode and root.children:
            mcts._add_dirichlet_noise(root, len(root.children) + len(root.pending))

        leaf_nodes: List[MCTSNode] = []
        for sim_idx in range(num_simulations):
            mcts._progressive_widen(root, sim_idx)
            node = mcts._select(root)
            leaf_nodes.append(node)

        leaf_values = mcts._batch_evaluate_leaves(
            root_state_vec=state_vec,
            nodes=leaf_nodes,
            base_value=base_value,
            state=world_state,
            legal_actions=legal_actions,
            world_seed=world_idx,
        )

        for node, lv in zip(leaf_nodes, leaf_values):
            mcts._backpropagate(node, lv)

        best_idx = mcts._select_action(root, legal_actions, training_mode)
        summary = _extract_level1_summary(root, best_idx, world_idx)
        conn.send(("done", summary))

    except Exception as e:
        logger.error(f"Erro no worker direct_gpu ISMCTS mundo {world_idx}: {e}", exc_info=True)
        try:
            conn.send(("done", {
                "world_idx": world_idx,
                "best_idx": 0,
                "root_stats": {},
                "children_stats": {},
                "error": str(e),
            }))
        except Exception:
            pass
    finally:
        try:
            conn.close()
        except Exception:
            pass


class ISMCTSEngine:
    """
    Information Set MCTS para Flesh and Blood (informação imperfeita).

    Estratégia:
      1. Gera W mundos determinizados preenchendo a mão oculta do oponente.
      2. Em cada mundo, roda MCTSEngine com batch leaf evaluation.
      3. Agrega votos: a ação com maior total de visit_counts entre mundos é escolhida.

    Número de mundos: calculado em startup via hardware scan (_probe_inference_latency_ms)
    e armazenado em SETTINGS.ismcts_worlds — proporcional à latência real medida.

    Referência: Cowling, Powley & Whitehouse (2012), IEEE Transactions on Games.
    """

    def __init__(
        self,
        model: Optional[FaBPolicyValueNetwork] = None,
        device: str = "cpu",
        c_puct: Optional[float] = None,
        num_worlds: Optional[int] = None,
        concurrency_mode: Optional[str] = None,
    ):
        self.model            = model
        self.device           = device
        self.c_puct           = c_puct if c_puct is not None else _get_c_puct()
        self.num_worlds       = num_worlds if num_worlds is not None else _get_ismcts_worlds()
        self.concurrency_mode = concurrency_mode
        self._cached_cpu_model: Optional[Any] = None

        self._mcts = MCTSEngine(
            model=model,
            device=device,
            c_puct=self.c_puct,
            single_player_tree=True,
        )

    def set_model(self, model: FaBPolicyValueNetwork, device: str = None) -> None:
        self.model            = model
        self.device           = device or self.device
        self._mcts.model      = model
        self._mcts.device     = self.device
        self._cached_cpu_model = None

    def _get_worker_model_for_direct_gpu(self) -> Optional[Any]:
        """
        Retorna uma versão segura para IPC/spawn do modelo (em CPU).
        No WSL2/Linux, passar tensores CUDA diretamente entre processos spawnados
        falha com 'CUDA error: invalid resource handle' devido a limitações de CUDA IPC.
        Garante que o modelo seja transmitido com tensores na CPU,
        permitindo que o worker faça model.to(device) em seu próprio contexto de processo.
        """
        if self.model is None:
            return None
        if not hasattr(self.model, "parameters"):
            return self.model
        try:
            has_cuda = any(getattr(p, "is_cuda", False) for p in self.model.parameters())
            if not has_cuda:
                return self.model
        except Exception:
            return self.model

        if self._cached_cpu_model is not None:
            try:
                self._cached_cpu_model.load_state_dict(
                    {k: v.cpu() for k, v in self.model.state_dict().items()}
                )
                return self._cached_cpu_model
            except Exception:
                self._cached_cpu_model = None

        try:
            from ai.model import FaBCardTransformerNetwork
            cpu_model = FaBCardTransformerNetwork()
            cpu_state = {k: v.detach().cpu() for k, v in self.model.state_dict().items()}
            cpu_model.load_state_dict(cpu_state)
            self._cached_cpu_model = cpu_model
            return self._cached_cpu_model
        except Exception as e:
            logger.warning(f"Aviso ao preparar modelo CPU para worker direct_gpu: {e}")
            return self.model

    # ── API pública ────────────────────────────────────────────────

    def search_ismcts(
        self,
        state: Dict[str, Any],
        legal_actions: List[Dict[str, Any]],
        num_simulations: int = 25,
        training_mode: bool = False,
        use_multiprocessing: Optional[bool] = None,
        concurrency_mode: Optional[str] = None,
    ) -> Tuple[int, np.ndarray, Dict[str, Any]]:
        """
        Executa ISMCTS via Concorrência Híbrida e retorna (best_idx, policy_dist, ismcts_log).

        Modos suportados (concurrency_mode):
          - 'threads' (Padrão/Estável): ThreadPoolExecutor in-process com 0 MB de overhead de processos.
          - 'multiprocessing': Pipeline Actor-Evaluator com mp.get_context("spawn") e BatchedInferenceServer via Pipes.
          - 'direct_gpu': Workers spawnados executando diretamente na GPU sem IPC.
          - 'sequential': Loop sequencial simples in-process para 1 mundo por vez.

        Returns:
            best_action_idx : Índice da melhor ação em `legal_actions`.
            policy_dist     : np.ndarray (32,) distribuição de votos normalizada.
            ismcts_log      : Dict com diagnóstico completo e estatísticas de Nível 1.
        """
        num_legal = len(legal_actions)
        if num_legal == 0:
            return 0, np.zeros(32, dtype=np.float32), {}

        # Vetor raiz base: para telemetria de diagnóstico
        state_vec = FaBPolicyValueNetwork.extract_state_vector(state)

        worlds = generate_worlds(state=state, opp_hand_count=None, num_worlds=self.num_worlds)
        actual_worlds = len(worlds)
        if actual_worlds == 0:
            return 0, np.zeros(32, dtype=np.float32), {}

        # Resolução do modo de concorrência ativo
        mode = concurrency_mode or self.concurrency_mode
        if mode is None:
            if use_multiprocessing is not None:
                mode = "multiprocessing" if use_multiprocessing else "sequential"
            else:
                try:
                    from config.settings import SETTINGS
                    mode = getattr(SETTINGS, "default_ismcts_concurrency", "threads")
                except Exception:
                    mode = "threads"

        mode = str(mode).lower()
        if mode not in ("threads", "multiprocessing", "direct_gpu", "sequential"):
            mode = "threads"

        results: List[Dict[str, Any]] = []

        if mode == "threads":
            try:
                max_workers = min(4, actual_worlds)
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    futures = [
                        executor.submit(
                            self._run_world_mcts,
                            world_state=world_state,
                            legal_actions=legal_actions,
                            num_simulations=num_simulations,
                            training_mode=training_mode,
                            state_vec=FaBPolicyValueNetwork.extract_state_vector(world_state),
                            world_seed=idx,
                        )
                        for idx, world_state in enumerate(worlds)
                    ]
                    for idx, future in enumerate(futures):
                        try:
                            best_idx_w, root = future.result()
                            results.append(_extract_level1_summary(root, best_idx_w, idx))
                        except Exception as e:
                            logger.error(f"Erro no thread worker ISMCTS mundo {idx}: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Falha no modo threads do ISMCTS: {e}. Executando fallback.", exc_info=True)
                results = []

        elif mode == "multiprocessing":
            ctx = mp.get_context("spawn")
            server_pipes = []
            worker_pipes = []
            processes = []

            try:
                for idx, world_state in enumerate(worlds):
                    p_serv, p_work = ctx.Pipe(duplex=True)
                    server_pipes.append(p_serv)
                    worker_pipes.append(p_work)

                    world_vec = FaBPolicyValueNetwork.extract_state_vector(world_state)
                    proc = ctx.Process(
                        target=_ismcts_worker_process,
                        args=(
                            p_work,
                            idx,
                            world_state,
                            legal_actions,
                            num_simulations,
                            training_mode,
                            self.c_puct,
                            world_vec,
                        ),
                    )
                    processes.append(proc)
                    proc.start()

                # Fecha referências do processo pai para os pipes dos workers
                for p_work in worker_pipes:
                    try:
                        p_work.close()
                    except Exception:
                        pass
                worker_pipes.clear()

                server = BatchedInferenceServer(model=self.model, device=self.device)
                results = server.serve(server_pipes, timeout=30.0)

            except Exception as e:
                logger.error(f"Falha na execução Actor-Evaluator do ISMCTS: {e}. Executando fallback.", exc_info=True)
                results = []
            finally:
                for p in worker_pipes:
                    try:
                        p.close()
                    except Exception:
                        pass
                for proc in processes:
                    proc.join(timeout=1.0)
                    if proc.is_alive():
                        proc.terminate()
                        proc.join(timeout=0.5)
                        if proc.is_alive():
                            proc.kill()
                            proc.join(timeout=0.2)
                        if proc.is_alive():
                            proc.kill()
                            proc.join(timeout=0.2)
                for p in server_pipes:
                    try:
                        p.close()
                    except Exception:
                        pass

        elif mode == "direct_gpu":
            ctx = mp.get_context("spawn")
            server_pipes = []
            worker_pipes = []
            processes = []

            # Obtém versão segura em CPU do modelo para evitar erro de CUDA IPC no spawn
            worker_model = self._get_worker_model_for_direct_gpu()

            try:
                for idx, world_state in enumerate(worlds):
                    p_serv, p_work = ctx.Pipe(duplex=True)
                    server_pipes.append(p_serv)
                    worker_pipes.append(p_work)

                    world_vec = FaBPolicyValueNetwork.extract_state_vector(world_state)
                    proc = ctx.Process(
                        target=_ismcts_direct_gpu_worker_process,
                        args=(
                            p_work,
                            idx,
                            world_state,
                            legal_actions,
                            num_simulations,
                            training_mode,
                            self.c_puct,
                            world_vec,
                            self.device,
                            worker_model,
                        ),
                    )
                    processes.append(proc)
                    proc.start()

                for p_work in worker_pipes:
                    try:
                        p_work.close()
                    except Exception:
                        pass
                worker_pipes.clear()

                results = []
                for p_serv in server_pipes:
                    try:
                        if p_serv.poll(timeout=30.0):
                            msg = p_serv.recv()
                            if isinstance(msg, tuple) and len(msg) == 2 and msg[0] == "done":
                                results.append(msg[1])
                    except Exception as e:
                        logger.error(f"Erro ao coletar resultado direct_gpu: {e}")

            except Exception as e:
                logger.error(f"Falha na execução direct_gpu do ISMCTS: {e}. Executando fallback.", exc_info=True)
                results = []
            finally:
                for p in worker_pipes:
                    try:
                        p.close()
                    except Exception:
                        pass
                for proc in processes:
                    proc.join(timeout=1.0)
                    if proc.is_alive():
                        proc.terminate()
                        proc.join(timeout=0.5)
                        if proc.is_alive():
                            proc.kill()
                            proc.join(timeout=0.2)
                        if proc.is_alive():
                            proc.kill()
                            proc.join(timeout=0.2)
                for p in server_pipes:
                    try:
                        p.close()
                    except Exception:
                        pass

        elif mode == "sequential":
            results = []
            for idx, world_state in enumerate(worlds):
                world_vec = FaBPolicyValueNetwork.extract_state_vector(world_state)
                best_idx_w, root = self._run_world_mcts(
                    world_state=world_state,
                    legal_actions=legal_actions,
                    num_simulations=num_simulations,
                    training_mode=training_mode,
                    state_vec=world_vec,
                    world_seed=idx,
                )
                results.append(_extract_level1_summary(root, best_idx_w, idx))

        # Fallback sequencial / in-process se nenhum resultado válido for retornado
        used_fallback = False
        if not results or not any(s.get("children_stats") for s in results):
            used_fallback = True
            logger.warning(f"ISMCTS modo '{mode}' não retornou resultados válidos. Executando fallback sequencial.")
            results = []
            for idx, world_state in enumerate(worlds):
                world_vec = FaBPolicyValueNetwork.extract_state_vector(world_state)
                best_idx_w, root = self._run_world_mcts(
                    world_state=world_state,
                    legal_actions=legal_actions,
                    num_simulations=num_simulations,
                    training_mode=training_mode,
                    state_vec=world_vec,
                    world_seed=idx,
                )
                results.append(_extract_level1_summary(root, best_idx_w, idx))

        # ── Agregação de Votos e Estatísticas Nível 1 ───────────────
        vote_counts: Dict[int, int] = {i: 0 for i in range(num_legal)}
        q_value_sums: Dict[int, float] = {i: 0.0 for i in range(num_legal)}
        prior_sums: Dict[int, float] = {i: 0.0 for i in range(num_legal)}
        world_counts: Dict[int, int] = {i: 0 for i in range(num_legal)}

        for summary in results:
            children_stats = summary.get("children_stats", {})
            for act_idx_raw, stats in children_stats.items():
                try:
                    act_idx = int(act_idx_raw)
                except (ValueError, TypeError):
                    continue
                if 0 <= act_idx < num_legal:
                    vc = stats.get("visit_count", 0)
                    vote_counts[act_idx] += vc
                    q_value_sums[act_idx] += stats.get("q_value", 0.0)
                    prior_sums[act_idx] += stats.get("prior", 0.0)
                    world_counts[act_idx] += 1

        total_votes = sum(vote_counts.values())
        policy_dist = np.zeros(32, dtype=np.float32)
        best_idx, best_votes = 0, -1

        if total_votes > 0:
            for idx, votes in vote_counts.items():
                if idx < num_legal:
                    act_mode = legal_actions[idx].get("mode", 99)
                    dist_idx = min(act_mode, 31) if act_mode < 32 else (act_mode % 32)
                    policy_dist[dist_idx] += votes / total_votes
            
            best_idx = max(vote_counts.keys(), key=lambda i: vote_counts[i] + 0.3 * (q_value_sums.get(i, 0.0) / max(1, vote_counts.get(i, 1))))
            best_votes = vote_counts[best_idx]
        else:
            # Fallback: heurística de scores táticos
            scored = sorted(enumerate(legal_actions), key=lambda x: x[1].get("score", 0), reverse=True)
            best_idx = scored[0][0] if scored else 0

        confidence = best_votes / total_votes if total_votes > 0 else 0.0

        # ── Log de Diagnóstico e Telemetria Nível 1 ────────────────
        _, base_value = self._mcts._evaluate(state_vec)
        action_names = [a.get("name", str(i)) for i, a in enumerate(legal_actions)]
        chosen_name = action_names[best_idx] if best_idx < len(action_names) else str(best_idx)

        level1_summary = {}
        for i in range(num_legal):
            act_name = action_names[i]
            cnt = max(world_counts.get(i, 0), 1)
            level1_summary[act_name] = {
                "action_id": i,
                "votes": vote_counts.get(i, 0),
                "mean_q": round(q_value_sums.get(i, 0.0) / cnt, 4),
                "mean_prior": round(prior_sums.get(i, 0.0) / cnt, 4),
            }

        ismcts_log = {
            "worlds_sampled"  : actual_worlds,
            "num_simulations" : num_simulations,
            "candidates"      : action_names,
            "votes"           : {action_names[i]: vote_counts.get(i, 0) for i in range(num_legal)},
            "chosen"          : chosen_name,
            "chosen_idx"      : best_idx,
            "confidence"      : round(confidence, 4),
            "mcts_value_root" : round(float(base_value), 4),
            "total_votes"     : total_votes,
            "level1_summary"  : level1_summary,
            "concurrency_mode": mode,
            "fallback"        : used_fallback,
        }

        return best_idx, policy_dist, ismcts_log

    # ── Helpers internos ──────────────────────────────────────────

    def _run_world_mcts(
        self,
        world_state: Dict[str, Any],
        legal_actions: List[Dict[str, Any]],
        num_simulations: int,
        training_mode: bool,
        state_vec: np.ndarray,
        world_seed: int = 0,
    ) -> Tuple[int, MCTSNode]:
        """
        Executa MCTSEngine em um mundo determinizado com batch leaf evaluation.

        Retorna (best_idx, root) para extração de estatísticas e vote_counts.
        Reutiliza o `state_vec` da raiz entre mundos — os mundos diferem apenas
        na mão oculta do oponente, não no vetor de estado do próprio bot.
        """
        num_legal = len(legal_actions)
        if num_legal == 0:
            return 0, MCTSNode(prior=1.0)

        priors, base_value = self._mcts._evaluate(state_vec)

        root = MCTSNode(prior=1.0)
        self._mcts._expand(root, legal_actions, priors)

        if training_mode and root.children:
            self._mcts._add_dirichlet_noise(root, len(root.children) + len(root.pending))

        # ── Phase 1, 2, 3: Simulate, Evaluate, Backpropagate ──────
        for sim_idx in range(num_simulations):
            self._mcts._progressive_widen(root, sim_idx)
            node = self._mcts._select(root)
            leaf_value = self._mcts._batch_evaluate_leaves(
                root_state_vec=state_vec,
                nodes=[node],
                base_value=base_value,
                state=world_state,
                legal_actions=legal_actions,
                world_seed=world_seed,
            )[0]
            self._mcts._backpropagate(node, leaf_value)

        best_idx = self._mcts._select_action(root, legal_actions, training_mode)
        return best_idx, root

