"""
FaB Talishar AI - Bot Client
Ponto de entrada do cliente HTTP de execução do bot em partidas.
Decomposto e modularizado no pacote ai.bot_runtime.
"""
import os
import argparse
from ai.bot_runtime import FabBotClient

__all__ = ["FabBotClient"]

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--room', required=True)
    parser.add_argument('--deck', required=True)
    parser.add_argument('--role', choices=['host', 'join'], required=True)
    parser.add_argument('--name', required=True)
    parser.add_argument('--mcts-sims', type=int, default=None)
    parser.add_argument('--device', type=str, default=None)
    parser.add_argument('--buffer-capacity', type=int, default=None)
    parser.add_argument('--epoch-ratio', type=float, default=0.0)
    parser.add_argument('--ismcts-concurrency', choices=['threads', 'multiprocessing', 'direct_gpu', 'sequential'], default=None)
    args = parser.parse_args()

    os.makedirs('logs', exist_ok=True)
    with open(f'logs/{args.room}_{args.name}_debug.log', 'a') as f:
        f.write('--- INICIO HTTP ---\n')
    
    client = FabBotClient(
        args.room, args.deck, args.role, args.name,
        mcts_sims=args.mcts_sims, device=args.device,
        buffer_capacity=args.buffer_capacity,
        epoch_ratio=args.epoch_ratio,
        ismcts_concurrency=args.ismcts_concurrency
    )
    client.run_loop()
