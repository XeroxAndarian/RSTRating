from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Iterable, List, Optional, Tuple

import pandas as pd


def _read_weekly_report(csv_path: Path) -> pd.DataFrame:
		"""Load a single weekly report CSV with robust header parsing."""
		with csv_path.open("r", encoding="utf-8", newline="") as handle:
			reader = csv.reader(handle, delimiter=";")
			rows = list(reader)

		if not rows:
			return pd.DataFrame()

		header_cells = rows[0]
		data_rows = rows[1:]
		max_cols = max((len(row) for row in data_rows), default=len(header_cells))

		if header_cells and "," in header_cells[0]:
			first_parts = header_cells[0].split(",", 1)
			header_cells = first_parts + header_cells[1:]

		if len(header_cells) > max_cols:
			header_cells = header_cells[:max_cols]
		elif len(header_cells) < max_cols:
			padding = [f"col_{i}" for i in range(len(header_cells), max_cols)]
			header_cells = header_cells + padding

		unique_headers = _make_unique_headers(header_cells)

		normalized_rows = [
			(row + [""] * (len(unique_headers) - len(row)))[: len(unique_headers)]
			for row in data_rows
		]

		df = pd.DataFrame(normalized_rows, columns=unique_headers)

		df.columns = [str(col).strip() for col in df.columns]

		if "date" not in df.columns and "date,id" in df.columns:
				df = df.rename(columns={"date,id": "date"})

		return df


def _make_unique_headers(headers: List[str]) -> List[str]:
		seen: dict[str, int] = {}
		unique: List[str] = []
		for header in headers:
			name = str(header).strip() or "column"
			if name in seen:
				seen[name] += 1
				unique.append(f"{name}_{seen[name]}")
			else:
				seen[name] = 0
				unique.append(name)
		return unique


def _normalize_numeric(series: pd.Series) -> pd.Series:
		cleaned = (
				series.astype(str)
				.str.replace(" ", "", regex=False)
				.str.replace(",", ".", regex=False)
		)
		return pd.to_numeric(cleaned, errors="coerce")


def _find_numeric_columns(df: pd.DataFrame, exclude: Iterable[str]) -> List[str]:
		numeric_cols: List[str] = []
		for col in df.columns:
				if col in exclude:
						continue
				numeric_series = _normalize_numeric(df[col])
				if numeric_series.notna().any():
						df[col] = numeric_series
						numeric_cols.append(col)
		return numeric_cols


def _prepare_weekly_report_data(reports_dir: str | Path) -> Tuple[List[dict], List[str], List[dict], List[str]]:
		reports_path = Path(reports_dir)
		csv_files = sorted(reports_path.glob("*.csv"))

		if not csv_files:
			raise FileNotFoundError(f"No CSV files found in {reports_path}")

		frames: List[pd.DataFrame] = []
		for csv_file in csv_files:
			df = _read_weekly_report(csv_file)
			if df.empty:
				continue

			if "id" not in df.columns:
				df.insert(1, "id", pd.NA)

			if "name" not in df.columns:
				df["name"] = "Unknown"

			if "surname" not in df.columns:
				df["surname"] = ""

			df["player"] = (
				df["name"].fillna("").astype(str).str.strip()
				+ " "
				+ df["surname"].fillna("").astype(str).str.strip()
			).str.strip()

			if "id" in df.columns:
				df["player"] = df["player"] + " (id " + df["id"].astype(str) + ")"

			frames.append(df)

		if not frames:
			raise ValueError("No valid data found in weekly reports.")

		data = pd.concat(frames, ignore_index=True)
		data["date"] = pd.to_datetime(data.get("date"), errors="coerce")
		data = data.dropna(subset=["date"])
		data["date"] = data["date"].dt.strftime("%Y-%m-%d")

		exclude_cols = {
			"date",
			"name",
			"surname",
			"player",
			"title",
			"best teammate",
			"worst teammate",
			"last match played",
			"rank",
		}

		numeric_cols = _find_numeric_columns(data, exclude_cols)
		if not numeric_cols:
			raise ValueError("No numeric stats found for plotting.")

		plot_df = data[["date", "player"] + numeric_cols].copy()
		plot_df = plot_df.dropna(subset=["player"])

		players = sorted(plot_df["player"].unique().tolist())
		player_meta = (
			plot_df[["player"]].drop_duplicates().merge(
				data[["player", "name", "surname", "id"]].drop_duplicates(),
				on="player",
				how="left",
			)
		)
		player_meta["name"] = player_meta["name"].fillna("").astype(str).str.strip()
		player_meta["surname"] = player_meta["surname"].fillna("").astype(str).str.strip()
		player_meta["id"] = player_meta["id"].fillna("").astype(str).str.strip()
		players_data = player_meta.to_dict(orient="records")

		records = plot_df.to_dict(orient="records")
		return records, players, players_data, numeric_cols


def create_weekly_report_line_graph(
	reports_dir: str | Path,
	output_html: str | Path,
	default_stat: Optional[str] = None,
	max_players: int = 12,
	default_date_range: Optional[Tuple[str, str]] = None,
) -> Path:
		"""
		Create an interactive HTML line graph for weekly player reports.

		Parameters:
				reports_dir: Folder with weekly CSV reports.
				output_html: Output HTML file path.
				default_stat: Optional stat to pre-select in the dropdown.
				max_players: Number of players selected by default.
		"""
		output_path = Path(output_html)
		records, players, players_data, stats = _prepare_weekly_report_data(reports_dir)

		if default_stat not in stats:
			default_stat = stats[0]

		default_start, default_end = ("", "")
		if default_date_range:
			default_start, default_end = default_date_range

		html_content = f"""<!doctype html>
<html lang=\"en\">
<head>
	<meta charset=\"utf-8\" />
	<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
	<title>Weekly Player Stats</title>
	<script src=\"https://cdn.plot.ly/plotly-2.27.0.min.js\"></script>
	<style>
		body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #0f172a; color: #e2e8f0; }}
		.container {{ display: grid; grid-template-columns: 320px 1fr; height: 100vh; }}
		.sidebar {{ background: #111827; padding: 16px; overflow: hidden; border-right: 1px solid #1f2937; box-sizing: border-box; }}
		.content {{ padding: 16px; }}
		h1 {{ font-size: 18px; margin: 0 0 12px; }}
		label, select, input {{ display: block; width: 100%; margin-bottom: 10px; }}
		select, input {{ padding: 8px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; }}
		.player-list {{ max-height: calc(100vh - 320px); overflow-y: auto; border: 1px solid #334155; border-radius: 6px; padding: 8px; }}
		.player-item {{ display: flex; align-items: center; gap: 6px; padding: 4px 0; }}
		.player-item input {{ width: 14px; height: 14px; flex: 0 0 14px; }}
		.player-name {{ font-size: 12px; line-height: 1.2; flex: 1; }}
		.actions {{ display: flex; gap: 8px; margin-bottom: 10px; }}
		button {{ flex: 1; padding: 8px; border-radius: 6px; border: 1px solid #334155; background: #1f2937; color: #e2e8f0; cursor: pointer; }}
		button:hover {{ background: #374151; }}
		#chart {{ height: 90vh; }}
	</style>
</head>
<body>
	<div class=\"container\">
		<aside class=\"sidebar\">
			<h1>Filters</h1>
			<label for=\"stat-select\">Stat</label>
			<select id=\"stat-select\"></select>

			<label for=\"date-start\">Start date</label>
			<input id=\"date-start\" type=\"date\" />

			<label for=\"date-end\">End date</label>
			<input id=\"date-end\" type=\"date\" />

			<label for=\"player-sort\">Order players by</label>
			<select id=\"player-sort\">
				<option value=\"name\">Name</option>
				<option value=\"surname\">Surname</option>
				<option value=\"id\">ID</option>
			</select>

			<label for=\"player-filter\">Filter players</label>
			<input id=\"player-filter\" type=\"text\" placeholder=\"Type to filter...\" />

			<div class=\"actions\">
				<button id=\"select-all\" type=\"button\">Select all</button>
				<button id=\"select-none\" type=\"button\">Select none</button>
			</div>

			<div id=\"player-list\" class=\"player-list\"></div>
		</aside>

		<main class=\"content\">
			<div id=\"chart\"></div>
		</main>
	</div>

	<script>
		const data = {json.dumps(records, ensure_ascii=False)};
		const players = {json.dumps(players, ensure_ascii=False)};
		const playersData = {json.dumps(players_data, ensure_ascii=False)};
		const stats = {json.dumps(stats, ensure_ascii=False)};
		const defaultStat = {json.dumps(default_stat, ensure_ascii=False)};
		const maxPlayers = {max_players};
		const defaultDateStart = {json.dumps(default_start, ensure_ascii=False)};
		const defaultDateEnd = {json.dumps(default_end, ensure_ascii=False)};

		const statSelect = document.getElementById('stat-select');
		const playerFilter = document.getElementById('player-filter');
		const playerSort = document.getElementById('player-sort');
		const playerList = document.getElementById('player-list');
		const dateStart = document.getElementById('date-start');
		const dateEnd = document.getElementById('date-end');

		function buildStatOptions() {{
			stats.forEach(stat => {{
				const option = document.createElement('option');
				option.value = stat;
				option.textContent = stat;
				if (stat === defaultStat) option.selected = true;
				statSelect.appendChild(option);
			}});
		}}

		function buildPlayerList() {{
			const selectedBefore = new Set(getSelectedPlayers());
			const sortKey = playerSort.value;
			const sortedPlayers = [...playersData].sort((a, b) => {{
				if (sortKey === 'id') {{
					const aId = parseInt(a.id || '0', 10);
					const bId = parseInt(b.id || '0', 10);
					return aId - bId;
				}}
				const aVal = (a[sortKey] || '').toString();
				const bVal = (b[sortKey] || '').toString();
				return aVal.localeCompare(bVal, 'sl', {{ sensitivity: 'base' }});
			}});

			playerList.innerHTML = '';
			sortedPlayers.forEach((playerInfo, index) => {{
				const player = playerInfo.player;
				const item = document.createElement('label');
				item.className = 'player-item';

				const checkbox = document.createElement('input');
				checkbox.type = 'checkbox';
				checkbox.value = player;
				checkbox.checked = selectedBefore.size
					? selectedBefore.has(player)
					: index < Math.min(maxPlayers, players.length);
				checkbox.addEventListener('change', render);

				const span = document.createElement('span');
				span.textContent = player;
				span.className = 'player-name';

				item.appendChild(checkbox);
				item.appendChild(span);
				playerList.appendChild(item);
			}});
		}}

		function normalizeDate(value) {{
			return value ? value : null;
		}}

		function withinDateRange(dateValue, startValue, endValue) {{
			if (!dateValue) return false;
			if (startValue && dateValue < startValue) return false;
			if (endValue && dateValue > endValue) return false;
			return true;
		}}

		function getSelectedPlayers() {{
			return Array.from(playerList.querySelectorAll('input[type="checkbox"]'))
				.filter(checkbox => checkbox.checked)
				.map(checkbox => checkbox.value);
		}}

		function filterPlayerList() {{
			const query = playerFilter.value.toLowerCase();
			playerList.querySelectorAll('.player-item').forEach(item => {{
				const text = item.textContent.toLowerCase();
				item.style.display = text.includes(query) ? 'flex' : 'none';
			}});
		}}

		function buildTraces(selectedStat, selectedPlayers) {{
			const startValue = normalizeDate(dateStart.value);
			const endValue = normalizeDate(dateEnd.value);
			const traces = [];
			selectedPlayers.forEach(player => {{
				const playerData = data
					.filter(row => (
						row.player === player &&
						row[selectedStat] !== null &&
						row[selectedStat] !== undefined &&
						withinDateRange(row.date, startValue, endValue)
					))
					.sort((a, b) => a.date.localeCompare(b.date));

				traces.push({{
					x: playerData.map(row => row.date),
					y: playerData.map(row => row[selectedStat]),
					mode: 'lines+markers',
					name: player,
					line: {{ width: 2 }},
				}});
			}});
			return traces;
		}}

		function render() {{
			const selectedStat = statSelect.value;
			const selectedPlayers = getSelectedPlayers();

			const traces = buildTraces(selectedStat, selectedPlayers);
			const layout = {{
				title: `${{selectedStat}} over time`,
				paper_bgcolor: '#0f172a',
				plot_bgcolor: '#0f172a',
				font: {{ color: '#e2e8f0' }},
				xaxis: {{ title: 'Date', gridcolor: '#1f2937' }},
				yaxis: {{ title: selectedStat, gridcolor: '#1f2937' }},
				legend: {{ orientation: 'h' }},
				margin: {{ t: 40, l: 60, r: 20, b: 60 }},
			}};

			Plotly.newPlot('chart', traces, layout, {{ responsive: true }});
		}}

		document.getElementById('select-all').addEventListener('click', () => {{
			playerList.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
			render();
		}});

		document.getElementById('select-none').addEventListener('click', () => {{
			playerList.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
			render();
		}});

		statSelect.addEventListener('change', render);
		playerFilter.addEventListener('input', filterPlayerList);
		playerSort.addEventListener('change', () => {{
			buildPlayerList();
			filterPlayerList();
			render();
		}});
		dateStart.addEventListener('change', render);
		dateEnd.addEventListener('change', render);

		buildStatOptions();
		buildPlayerList();
		if (defaultDateStart) dateStart.value = defaultDateStart;
		if (defaultDateEnd) dateEnd.value = defaultDateEnd;
		render();
	</script>
</body>
</html>
"""

		output_path.parent.mkdir(parents=True, exist_ok=True)
		output_path.write_text(html_content, encoding="utf-8")
		return output_path


def export_weekly_report_html(
		reports_dir: str | Path,
		output_html: str | Path,
		default_stat: Optional[str] = None,
		max_players: int = 12,
		default_date_range: Optional[Tuple[str, str]] = None,
	) -> Path:
		"""Wrapper to export the weekly report HTML graph."""
		return create_weekly_report_line_graph(
			reports_dir=reports_dir,
			output_html=output_html,
			default_stat=default_stat,
			max_players=max_players,
			default_date_range=default_date_range,
		)


def create_weekly_report_line_graph_mobile(
	reports_dir: str | Path,
	output_html: str | Path,
	default_stat: Optional[str] = None,
	max_players: int = 8,
	default_date_range: Optional[Tuple[str, str]] = None,
) -> Path:
	"""Create a mobile-friendly HTML line graph for weekly player reports."""
	output_path = Path(output_html)
	records, players, players_data, stats = _prepare_weekly_report_data(reports_dir)

	if default_stat not in stats:
		default_stat = stats[0]

	default_start, default_end = ("", "")
	if default_date_range:
		default_start, default_end = default_date_range

	html_content = f"""<!doctype html>
<html lang=\"en\">
<head>
	<meta charset=\"utf-8\" />
	<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\" />
	<title>Weekly Player Stats (Mobile)</title>
	<script src=\"https://cdn.plot.ly/plotly-2.27.0.min.js\"></script>
	<style>
		body {{ font-family: Arial, sans-serif; margin: 0; padding: 0; background: #0f172a; color: #e2e8f0; }}
		header {{ padding: 12px 16px; border-bottom: 1px solid #1f2937; background: #111827; }}
		h1 {{ font-size: 16px; margin: 0; }}
		details {{ background: #111827; border-bottom: 1px solid #1f2937; padding: 8px 16px; }}
		summary {{ cursor: pointer; font-weight: 600; }}
		.filters {{ display: grid; grid-template-columns: 1fr 1fr; gap: 8px; margin-top: 8px; }}
		label {{ font-size: 12px; }}
		select, input {{ width: 100%; padding: 8px; border-radius: 6px; border: 1px solid #334155; background: #0f172a; color: #e2e8f0; }}
		.player-actions {{ display: flex; gap: 8px; margin-top: 8px; }}
		.player-actions button {{ flex: 1; padding: 8px; border-radius: 6px; border: 1px solid #334155; background: #1f2937; color: #e2e8f0; }}
		.player-list {{ margin-top: 8px; max-height: 240px; overflow-y: auto; border: 1px solid #334155; border-radius: 6px; padding: 8px; }}
		.player-item {{ display: flex; align-items: center; gap: 6px; padding: 4px 0; }}
		.player-item input {{ width: 16px; height: 16px; }}
		.player-name {{ font-size: 12px; line-height: 1.2; flex: 1; }}
		#chart {{ height: 62vh; padding: 8px; }}
	</style>
</head>
<body>
	<header>
		<h1>Weekly Player Stats</h1>
	</header>

	<details open>
		<summary>Filters</summary>
		<div class=\"filters\">
			<div>
				<label for=\"stat-select\">Stat</label>
				<select id=\"stat-select\"></select>
			</div>
			<div>
				<label for=\"player-sort\">Order by</label>
				<select id=\"player-sort\">
					<option value=\"name\">Name</option>
					<option value=\"surname\">Surname</option>
					<option value=\"id\">ID</option>
				</select>
			</div>
			<div>
				<label for=\"date-start\">Start</label>
				<input id=\"date-start\" type=\"date\" />
			</div>
			<div>
				<label for=\"date-end\">End</label>
				<input id=\"date-end\" type=\"date\" />
			</div>
			<div style=\"grid-column: 1 / -1;\">
				<label for=\"player-filter\">Filter players</label>
				<input id=\"player-filter\" type=\"text\" placeholder=\"Type to filter...\" />
			</div>
		</div>

		<div class=\"player-actions\">
			<button id=\"select-all\" type=\"button\">Select all</button>
			<button id=\"select-none\" type=\"button\">Select none</button>
		</div>

		<div id=\"player-list\" class=\"player-list\"></div>
	</details>

	<div id=\"chart\"></div>

	<script>
		const data = {json.dumps(records, ensure_ascii=False)};
		const players = {json.dumps(players, ensure_ascii=False)};
		const playersData = {json.dumps(players_data, ensure_ascii=False)};
		const stats = {json.dumps(stats, ensure_ascii=False)};
		const defaultStat = {json.dumps(default_stat, ensure_ascii=False)};
		const maxPlayers = {max_players};
		const defaultDateStart = {json.dumps(default_start, ensure_ascii=False)};
		const defaultDateEnd = {json.dumps(default_end, ensure_ascii=False)};

		const statSelect = document.getElementById('stat-select');
		const playerFilter = document.getElementById('player-filter');
		const playerSort = document.getElementById('player-sort');
		const playerList = document.getElementById('player-list');
		const dateStart = document.getElementById('date-start');
		const dateEnd = document.getElementById('date-end');

		function buildStatOptions() {{
			stats.forEach(stat => {{
				const option = document.createElement('option');
				option.value = stat;
				option.textContent = stat;
				if (stat === defaultStat) option.selected = true;
				statSelect.appendChild(option);
			}});
		}}

		function getSelectedPlayers() {{
			return Array.from(playerList.querySelectorAll('input[type="checkbox"]'))
				.filter(checkbox => checkbox.checked)
				.map(checkbox => checkbox.value);
		}}

		function buildPlayerList() {{
			const selectedBefore = new Set(getSelectedPlayers());
			const sortKey = playerSort.value;
			const sortedPlayers = [...playersData].sort((a, b) => {{
				if (sortKey === 'id') {{
					const aId = parseInt(a.id || '0', 10);
					const bId = parseInt(b.id || '0', 10);
					return aId - bId;
				}}
				const aVal = (a[sortKey] || '').toString();
				const bVal = (b[sortKey] || '').toString();
				return aVal.localeCompare(bVal, 'sl', {{ sensitivity: 'base' }});
			}});

			playerList.innerHTML = '';
			sortedPlayers.forEach((playerInfo, index) => {{
				const player = playerInfo.player;
				const item = document.createElement('label');
				item.className = 'player-item';

				const checkbox = document.createElement('input');
				checkbox.type = 'checkbox';
				checkbox.value = player;
				checkbox.checked = selectedBefore.size
					? selectedBefore.has(player)
					: index < Math.min(maxPlayers, players.length);
				checkbox.addEventListener('change', render);

				const span = document.createElement('span');
				span.textContent = player;
				span.className = 'player-name';

				item.appendChild(checkbox);
				item.appendChild(span);
				playerList.appendChild(item);
			}});
		}}

		function normalizeDate(value) {{
			return value ? value : null;
		}}

		function withinDateRange(dateValue, startValue, endValue) {{
			if (!dateValue) return false;
			if (startValue && dateValue < startValue) return false;
			if (endValue && dateValue > endValue) return false;
			return true;
		}}

		function filterPlayerList() {{
			const query = playerFilter.value.toLowerCase();
			playerList.querySelectorAll('.player-item').forEach(item => {{
				const text = item.textContent.toLowerCase();
				item.style.display = text.includes(query) ? 'flex' : 'none';
			}});
		}}

		function buildTraces(selectedStat, selectedPlayers) {{
			const startValue = normalizeDate(dateStart.value);
			const endValue = normalizeDate(dateEnd.value);
			const traces = [];
			selectedPlayers.forEach(player => {{
				const playerData = data
					.filter(row => (
						row.player === player &&
						row[selectedStat] !== null &&
						row[selectedStat] !== undefined &&
						withinDateRange(row.date, startValue, endValue)
					))
					.sort((a, b) => a.date.localeCompare(b.date));

				traces.push({{
					x: playerData.map(row => row.date),
					y: playerData.map(row => row[selectedStat]),
					mode: 'lines+markers',
					name: player,
					line: {{ width: 2 }},
				}});
			}});
			return traces;
		}}

		function render() {{
			const selectedStat = statSelect.value;
			const selectedPlayers = getSelectedPlayers();

			const traces = buildTraces(selectedStat, selectedPlayers);
			const layout = {{
				title: `${{selectedStat}} over time`,
				paper_bgcolor: '#0f172a',
				plot_bgcolor: '#0f172a',
				font: {{ color: '#e2e8f0' }},
				xaxis: {{ title: 'Date', gridcolor: '#1f2937' }},
				yaxis: {{ title: selectedStat, gridcolor: '#1f2937' }},
				legend: {{ orientation: 'h' }},
				margin: {{ t: 40, l: 50, r: 20, b: 60 }},
			}};

			Plotly.newPlot('chart', traces, layout, {{ responsive: true }});
		}}

		document.getElementById('select-all').addEventListener('click', () => {{
			playerList.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = true);
			render();
		}});

		document.getElementById('select-none').addEventListener('click', () => {{
			playerList.querySelectorAll('input[type="checkbox"]').forEach(cb => cb.checked = false);
			render();
		}});

		statSelect.addEventListener('change', render);
		playerFilter.addEventListener('input', filterPlayerList);
		playerSort.addEventListener('change', () => {{
			buildPlayerList();
			filterPlayerList();
			render();
		}});
		dateStart.addEventListener('change', render);
		dateEnd.addEventListener('change', render);

		buildStatOptions();
		buildPlayerList();
		if (defaultDateStart) dateStart.value = defaultDateStart;
		if (defaultDateEnd) dateEnd.value = defaultDateEnd;
		render();
	</script>
</body>
</html>
"""

	output_path.parent.mkdir(parents=True, exist_ok=True)
	output_path.write_text(html_content, encoding="utf-8")
	return output_path


def export_weekly_report_html_mobile(
	reports_dir: str | Path,
	output_html: str | Path,
	default_stat: Optional[str] = None,
	max_players: int = 8,
	default_date_range: Optional[Tuple[str, str]] = None,
) -> Path:
	"""Wrapper to export the mobile weekly report HTML graph."""
	return create_weekly_report_line_graph_mobile(
		reports_dir=reports_dir,
		output_html=output_html,
		default_stat=default_stat,
		max_players=max_players,
		default_date_range=default_date_range,
	)


if __name__ == "__main__":
	base_dir = Path(__file__).resolve().parents[1]
	reports_dir = base_dir / "Data" / "Player Weekly Reports"
	output_html = base_dir / "Data" / "Exports" / "weekly_report_graph.html"
	output_mobile_html = base_dir / "Data" / "Exports" / "weekly_report_graph_mobile.html"
	result = export_weekly_report_html(
		reports_dir=reports_dir,
		output_html=output_html,
		default_stat=None,
		max_players=12,
		default_date_range=None,
	)
	mobile_result = export_weekly_report_html_mobile(
		reports_dir=reports_dir,
		output_html=output_mobile_html,
		default_stat=None,
		max_players=8,
		default_date_range=None,
	)
	print(f"Weekly report HTML generated at: {result}")
	print(f"Weekly report mobile HTML generated at: {mobile_result}")
