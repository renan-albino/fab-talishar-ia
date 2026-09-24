"""
ai/training/assimilation.py
===========================
Módulo de assimilação acelerada pós-partida contra humanos.
Executa mini-ciclos de treinamento priorizado (PER) imediatamente após o término
de duelos contra jogadores humanos, permitindo que a rede neural incorpore as
novas jogadas e correções táticas antes do próximo confronto.
"""

import os
import time
import json
import threading
from typing import Dict, Any, Optional

from ai.logger import get_logger

import contextlib
@contextlib.contextmanager
def file_lock(path, timeout=5.0):
    try:
        from filelock import FileLock
        lock = FileLock(f"{path}.lock", timeout=timeout)
        with lock:
            yield
    except ImportError:
        lock_file = f"{path}.lock"
        start_t = time.time()
        fd = None
        while time.time() - start_t < timeout:
            try:
                fd = os.open(lock_file, os.O_CREAT | os.O_EXCL | os.O_RDWR)
                break
            except OSError:
                time.sleep(0.05)
        try:
            yield
        finally:
            if fd is not None:
                try:
                    os.close(fd)
                    os.remove(lock_file)
                except OSError:
                    pass
    except Exception as e:
        logger.warning(f"[file_lock] Aviso ao obter lock em {path}: {e}")
        yield

logger = get_logger("assimilation")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "data")
STATUS_FILE = os.path.join(DATA_DIR, ".human_assimilation.json")


def _atomic_json_save(data: Dict[str, Any], filepath: str, indent: int = 2) -> None:
    temp_file = f"{filepath}.tmp"
    with open(temp_file, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=indent)
    os.replace(temp_file, filepath)


atomic_json_save = _atomic_json_save


def get_assimilation_status() -> Dict[str, Any]:
    """
    Retorna o status atual de assimilação neural pós-partida.
    Estrutura:
      {
        "status": "idle" | "assimilating" | "completed" | "error",
        "room_id": str,
        "started_at": float,
        "finished_at": float,
        "message": str,
        "final_loss": float
      }
    """
    if not os.path.exists(STATUS_FILE):
        return {"status": "idle"}
    try:
        with open(STATUS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Proteção contra status travado (timeout de 90 segundos)
        if data.get("status") == "assimilating":
            started = data.get("started_at", 0)
            if time.time() - started > 90:
                data["status"] = "idle"
                data["message"] = "Assimilação expirou (timeout)."

        return data
    except Exception as e:
        logger.warning(f"Erro ao ler status de assimilação: {e}")
        return {"status": "idle"}


def clear_assimilation_status():
    """Reseta o status de assimilação para idle."""
    try:
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({"status": "idle", "timestamp": time.time()}, f, indent=2)
    except Exception as e:
        logger.warning(f"Erro ao resetar status de assimilação: {e}")


def _run_assimilation_job(room_id: str, bot_player_id: int, winner_id: int):
    """Executa a assimilação em background thread."""
    try:
        import torch
        import torch.nn.functional as F
        from config.settings import SETTINGS
        from ai.experience_collector import get_global_buffer
        from ai.model import create_model, get_device

        dev = get_device()
        buffer = get_global_buffer(SETTINGS.buffer_capacity)

        trajectories_dir = os.path.join(DATA_DIR, "trajectories")
        if os.path.exists(trajectories_dir):
            try:
                buffer.ingest_trajectories(trajectories_dir)
            except Exception as e:
                logger.warning(f"[Assimilation] Falha ao ingerir trajetórias: {e}")

        if len(buffer) < 8:
            logger.info("[Assimilation] Buffer insuficiente para treino imediato (< 8 amostras).")
            atomic_json_save({
                "status": "completed",
                "room_id": str(room_id),
                "finished_at": time.time(),
                "message": "Partida registrada no Replay Buffer (amostras insuficientes para treino em lote).",
                "final_loss": 0.0
            }, STATUS_FILE)
            return

        logger.info(f"[Assimilation] Iniciando assimilação pós-partida (Sala #{room_id}, Dispositivo: {dev})...")
        model, _ = create_model(device=dev)
        model.train()

        steps = getattr(SETTINGS, "human_post_match_training_steps", 10)
        batch_size = min(128, len(buffer))
        lr = 5e-5  # Fine-tuning rate conservador para assimilação suave
        optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=1e-4)

        last_loss = 0.0
        for step in range(steps):
            states_b, policies_b, values_b, is_weights_b, aux_targets = buffer.sample_batch(
                batch_size=batch_size,
                device=dev,
                prioritized=True,
                return_is_weights=True,
                return_aux=True,
            )

            optimizer.zero_grad()
            policy_logits, value_preds, aux_preds = model(states_b, return_aux=True)

            log_probs = F.log_softmax(policy_logits, dim=-1)
            sample_loss_policy = -(policies_b * log_probs).sum(dim=-1)
            sample_loss_value = (value_preds.squeeze(-1) - values_b.squeeze(-1)) ** 2

            loss_policy = (is_weights_b * sample_loss_policy).mean()
            loss_value = (is_weights_b * sample_loss_value).mean()

            loss_aux_delta = F.mse_loss(aux_preds["delta_hp"].squeeze(-1), aux_targets["delta_hp"].squeeze(-1))
            loss_aux_dmg = F.mse_loss(aux_preds["turn_dmg"].squeeze(-1), aux_targets["turn_dmg"].squeeze(-1))
            aux_loss = 0.2 * (loss_aux_delta + loss_aux_dmg)

            total_loss = loss_policy + loss_value + aux_loss
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()

            last_loss = float(total_loss.item())

        # Salva o checkpoint atualizado
        ckpt_path = os.path.join(DATA_DIR, "model_latest.pt")
        with file_lock(ckpt_path, timeout=5.0):
            torch.save(model.state_dict(), ckpt_path)
            
            # Save to both paths so bot and orchestrator both see updated weights
            teacher_ckpt = SETTINGS.teacher_checkpoint
            os.makedirs(os.path.dirname(teacher_ckpt), exist_ok=True)
            torch.save(model.state_dict(), teacher_ckpt)

        logger.info(f"[Assimilation] ✓ Assimilação concluída! {steps} passos de treino. Loss final: {last_loss:.4f}")

        # Notifica conclusão diretamente no log da sala do Talishar (se acessível)
        try:
            gamelog_path = os.path.join(BASE_DIR, "Talishar", "Games", str(room_id), "gamelog.txt")
            if os.path.exists(gamelog_path):
                done_msg = (
                    f"<div style='background:#14532d;border-left:4px solid #4ade80;padding:3px 6px;margin:2px 0;border-radius:4px;color:#4ade80;font-size:12px;'>"
                    f"✅ <b>[ASSIMILAÇÃO CONCLUÍDA!]</b> {steps} passos de treino finalizados (Loss: {last_loss:.4f}). "
                    f"Pesos de decisão atualizados com sucesso em <code>model_latest.pt</code>!</div>\n"
                )
                with open(gamelog_path, "a", encoding="utf-8") as gf:
                    gf.write(done_msg)
        except Exception:
            pass

        # Sincroniza samples_collected em training_metrics.json se o arquivo existir
        try:
            metrics_path = os.path.join(DATA_DIR, "training_metrics.json")
            if os.path.exists(metrics_path):
                with open(metrics_path, "r", encoding="utf-8") as mf:
                    mdata = json.load(mf)
                mdata["samples_collected"] = len(buffer)
                with open(metrics_path, "w", encoding="utf-8") as f:
                    json.dump(mdata, f, indent=2)
        except Exception:
            pass

        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "status": "completed",
                "room_id": str(room_id),
                "finished_at": time.time(),
                "message": f"Partida assimilada com sucesso ({steps} passos, loss: {last_loss:.4f}). Pesos neurais atualizados!",
                "final_loss": round(last_loss, 4),
            }, f, indent=2)

    except Exception as e:
        logger.error(f"[Assimilation] ❌ Falha na assimilação pós-partida: {e}", exc_info=True)
        with open(STATUS_FILE, "w", encoding="utf-8") as f:
            json.dump({
                "status": "error",
                "room_id": str(room_id),
                "finished_at": time.time(),
                "message": f"Erro durante a assimilação: {e}",
                "final_loss": 0.0,
            }, f, indent=2)


def trigger_human_match_assimilation(room_id: str, bot_player_id: int, winner_id: int, wait: bool = True):
    """
    Dispara a assimilação da partida contra humano.
    Atualiza o arquivo de status para o Dashboard e executa a assimilação,
    garantindo que o processo não seja finalizado abruptamente antes do término do treino.
    """
    status_data = {
        "status": "assimilating",
        "room_id": str(room_id),
        "started_at": time.time(),
        "message": f"A Rede Neural está assimilando as jogadas da Sala #{room_id} com treino prioritário...",
        "final_loss": 0.0,
    }
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status_data, f, indent=2)
    t = threading.Thread(
        target=_run_assimilation_job,
        args=(room_id, bot_player_id, winner_id),
        daemon=False,
        name=f"Assimilation-Room-{room_id}"
    )
    t.start()
    if wait:
        t.join(timeout=45.0)
