# Thingsboard Simulator (local)

Simule des télémétries Thingsboard à partir de `data/devices.ifc.json`.

## Pré-requis
- Python 3.9+

## Installation
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

## Lancer
```bash
python run_simulator.py
```

## Options
```bash
python run_simulator.py --base-url http://localhost:7000 --interval 5
```

## Notes
- Par défaut, le script lit `backend.baseUrl` dans `data/devices.ifc.json`.
- Si Thingsboard est exposé sur la machine hôte, utilisez généralement `http://localhost:7000`.
- Les télémétries sont envoyées sur `/api/v1/{accessToken}/telemetry`.
