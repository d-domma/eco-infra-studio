import json
import urllib.parse
import urllib.request

ua = {"User-Agent": "EcoInfraStudio/1.0"}
base = "https://data.cityofnewyork.us/resource/64uk-42ks.json"
tests = [
    {"$limit": "2", "$select": "bbl,numfloors,latitude,lotarea"},
    {"$limit": "2", "$where": "numfloors > 0"},
]
for params in tests:
    url = base + "?" + urllib.parse.urlencode(params)
    print("TRY", url)
    try:
        req = urllib.request.Request(url, headers=ua)
        with urllib.request.urlopen(req, timeout=40) as res:
            data = json.loads(res.read().decode())
        print(" ok", len(data), data[0] if data else None)
    except Exception as exc:
        print(" ERR", exc)
