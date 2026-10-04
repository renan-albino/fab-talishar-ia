import requests, json
deck_data = json.load(open('decks/teklovossen.json'))
payload = {
    'format': 'cc',
    'visibility': 'private',
    'gameDescription': 'test',
    'deck': json.dumps(deck_data)
}
res = requests.post('http://localhost:8080/game/APIs/CreateGame.php', json=payload)
print(res.text)
