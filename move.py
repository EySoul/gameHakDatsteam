import requests

domen = "https://games-test.datsteam.dev"
token = "d4d94a5f-c6aa-49af-b547-13897fb0896a"
prefix = "/api"

url = f"{domen}{prefix}/move"

headers = {"X-Auth-Token": token, "Content-Type": "application/json"}

# Assuming the bomber's ID is 'bomber1' and current position is [0, 0]
# To move right, add the next position [1, 0] to the path
# Note: In a real scenario, you would need to fetch or track the current position
data = {
    "bombers": [
        {"id": "32f6226f-145c-43c3-abf2-84bceef70484", "path": [[0, 0], [1, 0]]}
    ]
}

response = requests.post(url, json=data, headers=headers)

print("Response status:", response.status_code)
print("Response body:", response.json())
