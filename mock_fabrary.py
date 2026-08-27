from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import os

class MockFaBrary(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.end_headers()
        
        # Tenta ler o arquivo deck.json local se existir
        deck_path = "Talishar/deck.json" if os.path.exists("Talishar/deck.json") else "deck.json"
        if os.path.exists(deck_path):
            with open(deck_path, "r") as f:
                data = f.read()
            self.wfile.write(data.encode('utf-8'))
        else:
            deck = {
                "name": "Bot Deck Dinamico",
                "format": "blitz",
                "cards": [
                    {"identifier": "ira_crimson_haze", "total": 1},
                    {"identifier": "edge_of_autumn", "total": 1},
                    {"identifier": "blade_beckoner_helm", "total": 1},
                    {"identifier": "blood_scent", "total": 1},
                    {"identifier": "tearing_shuko", "total": 1},
                    {"identifier": "pouncing_paws", "total": 1},
                    {"identifier": "bittering_thorns_red", "total": 2},
                    {"identifier": "chest_puff_red", "total" : 2},
                    {"identifier": "cut_through_red", "total": 2},
                    {"identifier": "flying_kick_red", "total": 2},
                    {"identifier": "humble_red", "total": 2},
                    {"identifier": "on_the_horizon_red", "total": 2},
                    {"identifier": "pouncing_qi_red", "total": 2},
                    {"identifier": "razor_reflex_red", "total": 1},
                    {"identifier": "scar_for_a_scar_red", "total": 2},
                    {"identifier": "smash_up_red", "total": 2},
                    {"identifier": "snatch_red", "total": 2},
                    {"identifier": "torrent_of_tempo_red", "total": 2},
                    {"identifier": "up_sticks_and_run_red", "total": 2},
                    {"identifier": "tiger_eye_reflex_yellow", "total": 2},
                    {"identifier": "feign_vengeance_blue", "total": 2},
                    {"identifier": "fluster_fist_blue", "total": 2},
                    {"identifier": "legacy_of_ikaru_blue", "total": 2},
                    {"identifier": "nip_at_the_heels_blue", "total": 2},
                    {"identifier": "punch_above_your_weight_blue", "total": 1},
                    {"identifier": "seek_vengeance_blue", "total": 2},
                    {"identifier": "silver_talons_blue", "total": 2},
                    {"identifier": "soulbead_strike_blue", "total": 2}
                ]
            }
            self.wfile.write(json.dumps(deck).encode('utf-8'))

print("[*] FaBrary Falso rodando na porta 9000...")
HTTPServer(('0.0.0.0', 9000), MockFaBrary).serve_forever()