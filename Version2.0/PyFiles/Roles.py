import json
from collections import OrderedDict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA_BANK = ROOT / "Data" / "Data Bank" / "Data.json"
OUTPUT = ROOT / "Data" / "ROLES.json"


def load_players(path: Path) -> OrderedDict:
	with path.open("r", encoding="utf-8") as handle:
		return json.load(handle, object_pairs_hook=OrderedDict)


def build_roles(players: OrderedDict) -> OrderedDict:
	roles = OrderedDict()
	for key, value in players.items():
		if not isinstance(value, dict):
			continue
		name = str(value.get("name", "")).strip()
		surname = str(value.get("surname", "")).strip()
		role = str(value.get("role", "X")).strip().upper() or "X"
		if name or surname:
			full_name = f"{surname} {name}".strip()
			roles[full_name] = role
	return roles


def save_roles(path: Path, roles: OrderedDict) -> None:
	with path.open("w", encoding="utf-8") as handle:
		json.dump(roles, handle, ensure_ascii=False, indent=4)
		handle.write("\n")


def main() -> None:
	players = load_players(DATA_BANK)
	roles = build_roles(players)
	save_roles(OUTPUT, roles)
	print(f"Saved {len(roles)} roles to {OUTPUT}")


if __name__ == "__main__":
	main()
