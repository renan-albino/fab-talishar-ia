import requests, json
payload = {
    'format': 'cc',
    'visibility': 'private',
    'gameDescription': 'test',
    'fabdb': 'decks/teklovossen.json'
}
res = requests.post('http://localhost:8080/game/APIs/CreateGame.php', json=payload)
print(res.text)
