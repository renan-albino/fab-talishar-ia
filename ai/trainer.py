"""
ai/trainer.py
=============
GPUTrainingOrchestrator: Orquestrador de Treinamento Autônomo com GPU (PyTorch + CUDA).

Gerencia Self-Play paralelo, Replay Buffer e gradientes na GPU.
Todos os hiperparâmetros são lidos do config/settings.py com suporte a overrides da UI/CLI.
"""

import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

import time
import json
import threading
import subprocess
import uuid
import numpy as np
import torch
import torch.nn.functional as F
from typing import Dict, Any, List, Optional

from config.settings import SETTINGS
from ai.model import FaBPolicyValueNetwork, create_model
from ai.experience_collector import get_global_buffer

# ── Caminhos derivados do SETTINGS ───────────────────────────────
DATA_DIR      = os.path.join(BASE_DIR, "data")
METRICS_FILE  = os.path.join(DATA_DIR, "training_metrics.json")
os.makedirs(SETTINGS.checkpoint_dir, exist_ok=True)
os.makedirs(SETTINGS.parquet_export_dir, exist_ok=True)


class GPUTrainingOrchestrator:
    """
    Singleton que gerencia o loop de treinamento autônomo.
    """

    _instance = None

    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if getattr(self, "_initialized", False):
            return
        self._initialized = True
        self.is_running = False
        self.thread: Optional[threading.Thread] = None
        self.deck_rot_idx = 0
        self._extra: Dict[str, Any] = {}
        self.model: Optional[FaBPolicyValueNetwork] = None

        # Stats expostos ao dashboard (via polling)
        self.stats: Dict[str, Any] = {
            "total_games":      0,
            "samples_collected":0,
            "epochs_completed": 0,
            "policy_loss":      0.0,
            "value_loss":       0.0,
            "total_loss":       0.0,
            "active_matchup":   "Aguardando início...",
            "last_summary":     "Nenhuma partida concluída nesta sessão.",
            "history":          [],
            "policy_entropy":   0.0,
            "value_mean":       0.0,
            "current_phase":    SETTINGS.current_phase,
            "device":           SETTINGS.device,
            "batch_size":       SETTINGS.batch_size,
            "num_workers":      SETTINGS.num_workers,
            "mcts_sims":        SETTINGS.mcts_simulations,
            "max_resources":    SETTINGS.max_resources_mode,
        }
        self.load_metrics()

    @property
    def config(self) -> Dict[str, Any]:
        """Retorna o dicionário de configurações ativas mesclando SETTINGS e overrides."""
        return {
            "device":              self._extra.get("device", SETTINGS.device),
            "num_workers":         self._extra.get("num_workers", SETTINGS.num_workers),
            "batch_size":          self._extra.get("batch_size", SETTINGS.batch_size),
            "learning_rate":       self._extra.get("learning_rate", SETTINGS.learning_rate),
            "buffer_capacity":     self._extra.get("buffer_capacity", SETTINGS.buffer_capacity),
            "mcts_sims":           self._extra.get("mcts_sims", SETTINGS.mcts_simulations),
            "fp16":                self._extra.get("fp16", SETTINGS.fp16),
            "save_interval_games": self._extra.get("save_interval_games", SETTINGS.save_interval_games),
            "training_decks":      self._extra.get("training_decks", []),
            "max_resources":       SETTINGS.max_resources_mode,
        }

    # ── Métricas persistidas (API pública para dashboard) ────────

    def load_metrics(self):
        """Carrega métricas persistidas em disco."""
        if os.path.exists(METRICS_FILE):
            try:
                with open(METRICS_FILE, "r", encoding="utf-8") as f:
                    saved = json.load(f)
                    for key in ("total_games", "samples_collected", "epochs_completed",
                                "policy_loss", "value_loss", "total_loss", "history",
                                "policy_entropy", "value_mean"):
                        if key in saved:
                            self.stats[key] = saved[key]
            except Exception:
                pass

    def save_metrics(self):
        """Salva métricas e checkpoints em disco."""
        os.makedirs(DATA_DIR, exist_ok=True)
        try:
            with open(METRICS_FILE, "w", encoding="utf-8") as f:
                json.dump(self.stats, f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        # Salva o modelo e o buffer se existirem
        if self.model is not None:
            try:
                buffer = get_global_buffer(self.config.get("buffer_capacity", SETTINGS.buffer_capacity))
                self._save_checkpoint(self.model, buffer)
            except Exception as e:
                print(f"[Treinador] Aviso ao salvar checkpoint manual: {e}")

    # Aliases privados para compatibilidade interna
    _load_metrics = load_metrics
    _save_metrics = save_metrics

    # ── Controle externo ──────────────────────────────────────────

    def start(self, custom_config: Dict[str, Any] = None):
        """Inicia o loop de treinamento numa thread daemon."""
        if self.is_running:
            return
        self.is_running = True
        self._extra = custom_config or {}
        self.thread = threading.Thread(target=self._training_loop, daemon=True)
        self.thread.start()
        cfg = self.config
        print(f"[Treinador] ▶ Iniciado | Dispositivo: {cfg['device']} | Batch: {cfg['batch_size']} | Workers: {cfg['num_workers']}")

    def stop(self):
        """Sinaliza parada e aguarda a thread terminar (até 3s)."""
        self.is_running = False
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=3.0)
        print("[Treinador] ⏸ Treinamento pausado.")

    # ── Loop principal ────────────────────────────────────────────

    def _training_loop(self):
        cfg = self.config
        device_str = cfg.get("device", SETTINGS.device)
        device = torch.device(device_str)
        self.model, _ = create_model(device=str(device))

        learning_rate = float(cfg.get("learning_rate", SETTINGS.learning_rate))
        optimizer = torch.optim.AdamW(
            self.model.parameters(),
            lr=learning_rate,
            weight_decay=SETTINGS.weight_decay,
        )
        scheduler = torch.optim.lr_scheduler.StepLR(
            optimizer,
            step_size=SETTINGS.lr_scheduler_step,
            gamma=SETTINGS.lr_scheduler_gamma,
        )
        use_fp16 = bool(cfg.get("fp16", SETTINGS.fp16)) and "cuda" in str(device)
        scaler = torch.cuda.amp.GradScaler(enabled=use_fp16)

        buffer_cap = int(cfg.get("buffer_capacity", SETTINGS.buffer_capacity))
        buffer = get_global_buffer(buffer_cap)

        training_decks: List[str] = cfg.get("training_decks", [])
        num_workers = int(cfg.get("num_workers", SETTINGS.num_workers))
        batch_size = int(cfg.get("batch_size", SETTINGS.batch_size))
        save_interval = int(cfg.get("save_interval_games", SETTINGS.save_interval_games))

        py_bin = os.path.join(BASE_DIR, "venv", "bin", "python")
        if not os.path.exists(py_bin):
            py_bin = sys.executable

        games_since_save = 0

        while self.is_running:
            # ── 1. Selecionar par de decks (rotativo) ──────────────
            decks_pool = training_decks or self._get_all_decks()

            batch_rooms: List[tuple] = []
            active_procs: List[tuple] = []

            mcts_sims_val = self.config.get("mcts_sims", 25)
            dev_val = self.config.get("device", "cuda:0")

            for _ in range(num_workers):
                if not self.is_running:
                    break
                d1, d2 = self._next_deck_pair(decks_pool)
                room_id = f"Train_{uuid.uuid4().hex[:8]}"
                p1 = subprocess.Popen(
                    [py_bin, os.path.join(BASE_DIR, "bot_client.py"),
                     "--room", room_id, "--deck", f"decks/{d1}.json",
                     "--role", "host",  "--name", "Bot1",
                     "--mcts-sims", str(mcts_sims_val),
                     "--device", str(dev_val)],
                    cwd=BASE_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=lambda: os.nice(10) if hasattr(os, "nice") else None,
                )
                time.sleep(0.2)
                p2 = subprocess.Popen(
                    [py_bin, os.path.join(BASE_DIR, "bot_client.py"),
                     "--room", room_id, "--deck", f"decks/{d2}.json",
                     "--role", "join",  "--name", "Bot2",
                     "--mcts-sims", str(mcts_sims_val),
                     "--device", str(dev_val)],
                    cwd=BASE_DIR,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                    preexec_fn=lambda: os.nice(10) if hasattr(os, "nice") else None,
                )
                active_procs.append((p1, p2))
                batch_rooms.append((room_id, d1, d2))
                # Espaçamento suave para não sobrecarregar o Apache/PHP
                time.sleep(0.3)

            if batch_rooms:
                r0 = batch_rooms[0]
                extra_label = f" (+{len(batch_rooms)-1} partidas)" if len(batch_rooms) > 1 else ""
                self.stats["active_matchup"] = f"{r0[1]} vs {r0[2]}{extra_label}"

            # ── 2. Aguardar término das partidas (com timeout) ──────
            timeout = SETTINGS.game_timeout_seconds
            deadline = time.time() + timeout
            while time.time() < deadline and self.is_running:
                if all(p1.poll() is not None and p2.poll() is not None
                       for p1, p2 in active_procs):
                    break
                time.sleep(0.3)

            for p1, p2 in active_procs:
                if p1.poll() is None: p1.terminate()
                if p2.poll() is None: p2.terminate()

            self.stats["total_games"] += len(active_procs)
            games_since_save += len(active_procs)

            # ── 3. Atualizar ELO com resultados das partidas ────────
            for room_id, d1_slug, d2_slug in batch_rooms:
                self._update_elo(room_id, d1_slug, d2_slug)

            # ── 4. Carregar último sumário de partida ───────────────
            if batch_rooms:
                last_room = batch_rooms[-1][0]
                summary_file = os.path.join(BASE_DIR, "logs", f"{last_room}_summary.log")
                if os.path.exists(summary_file):
                    try:
                        with open(summary_file, "r", encoding="utf-8") as sf:
                            self.stats["last_summary"] = sf.read()
                    except Exception:
                        pass

            # ── 5. Recarregar buffer e passo de otimização ─────────
            buffer.load()
            self.stats["samples_collected"] = len(buffer)

            min_train = min(batch_size, max(32, len(buffer)))
            if len(buffer) >= min_train:
                loss_p, loss_v, loss_t, entropy, val_mean = self._train_step(
                    self.model, optimizer, scaler, buffer, device, batch_size, use_fp16
                )
                scheduler.step()

                self.stats["epochs_completed"] += 1
                self.stats["policy_loss"]    = round(loss_p, 4)
                self.stats["value_loss"]     = round(loss_v, 4)
                self.stats["total_loss"]     = round(loss_t, 4)
                self.stats["policy_entropy"] = round(entropy, 4)
                self.stats["value_mean"]     = round(val_mean, 4)

                epoch_entry = {
                    "epoch":        self.stats["epochs_completed"],
                    "policy_loss":  self.stats["policy_loss"],
                    "value_loss":   self.stats["value_loss"],
                    "total_loss":   self.stats["total_loss"],
                    "entropy":      self.stats["policy_entropy"],
                    "value_mean":   self.stats["value_mean"],
                    "games":        self.stats["total_games"],
                    "samples":      self.stats["samples_collected"],
                    "lr":           round(scheduler.get_last_lr()[0], 6),
                }
                self.stats["history"].append(epoch_entry)
                if len(self.stats["history"]) > 200:
                    self.stats["history"].pop(0)

            self.save_metrics()

            # ── 6. Salvar checkpoint periodicamente ─────────────────
            if games_since_save >= save_interval:
                games_since_save = 0
                self._save_checkpoint(self.model, buffer)

            time.sleep(0.05)

        # Ao parar, garante que salva o estado final
        if self.model is not None:
            self._save_checkpoint(self.model, buffer)
        self.save_metrics()

    # ── Helpers internos ──────────────────────────────────────────

    def _train_step(
        self,
        model: FaBPolicyValueNetwork,
        optimizer: torch.optim.Optimizer,
        scaler: torch.cuda.amp.GradScaler,
        buffer,
        device: torch.device,
        batch_size: int,
        use_amp: bool,
    ):
        model.train()
        eff_batch = min(batch_size, len(buffer))
        states_b, policies_b, values_b = buffer.sample_batch(
            batch_size=eff_batch, device=device
        )

        optimizer.zero_grad()

        with torch.cuda.amp.autocast(enabled=use_amp):
            policy_logits, value_preds = model(states_b)

            log_probs  = F.log_softmax(policy_logits, dim=-1)
            loss_policy = -(policies_b * log_probs).sum(dim=-1).mean()
            loss_value  = F.mse_loss(value_preds.squeeze(-1), values_b.squeeze(-1))
            total_loss  = loss_policy + loss_value

        scaler.scale(total_loss).backward()
        scaler.unscale_(optimizer)
        torch.nn.utils.clip_grad_norm_(model.parameters(), SETTINGS.grad_clip_norm)
        scaler.step(optimizer)
        scaler.update()

        with torch.no_grad():
            probs   = F.softmax(policy_logits, dim=-1)
            entropy = -(probs * (probs + 1e-9).log()).sum(dim=-1).mean().item() / np.log(2)
            val_mean = value_preds.mean().item()

        return (
            float(loss_policy.item()),
            float(loss_value.item()),
            float(total_loss.item()),
            entropy,
            val_mean,
        )

    def _next_deck_pair(self, pool: List[str]):
        if len(pool) >= 2:
            d1 = pool[self.deck_rot_idx % len(pool)]
            d2 = pool[(self.deck_rot_idx + 1) % len(pool)]
        elif len(pool) == 1:
            d1 = d2 = pool[0]
        else:
            d1 = d2 = "calling_hamburg_1st"
        self.deck_rot_idx += 1
        return d1, d2

    @staticmethod
    def _get_all_decks() -> List[str]:
        try:
            from deck_parser import list_saved_decks
            return [d["slug"] for d in list_saved_decks()]
        except Exception:
            return []

    @staticmethod
    def _update_elo(room_id: str, d1_slug: str, d2_slug: str):
        m1_path = os.path.join(BASE_DIR, "logs", f"{room_id}_Bot1.json")
        m2_path = os.path.join(BASE_DIR, "logs", f"{room_id}_Bot2.json")
        if not (os.path.exists(m1_path) and os.path.exists(m2_path)):
            return
        try:
            with open(m1_path) as f1:
                m1 = json.load(f1).get("metrics", {})
            with open(m2_path) as f2:
                m2 = json.load(f2).get("metrics", {})
            h1 = m1.get("health", 40)
            h2 = m2.get("health", 40)
            if h1 <= 0 or h2 <= 0:
                w_id = 1 if h2 <= 0 else 2
                from stats_manager import update_match_result
                update_match_result(
                    room_id, d1_slug, d2_slug,
                    h1, h2, m1.get("turn", 15), w_id
                )
        except Exception:
            pass

    @staticmethod
    def _save_checkpoint(model: FaBPolicyValueNetwork, buffer):
        os.makedirs(SETTINGS.checkpoint_dir, exist_ok=True)
        torch.save(model.state_dict(), SETTINGS.teacher_checkpoint)
        versioned = SETTINGS.teacher_checkpoint.replace(
            "teacher_latest.pt",
            f"teacher_epoch_{int(time.time())}.pt"
        )
        torch.save(model.state_dict(), versioned)
        buffer.save()
        print(f"[Treinador] 💾 Checkpoint salvo: {SETTINGS.teacher_checkpoint}")
