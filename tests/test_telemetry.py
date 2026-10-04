"""Tests for telemetry CSV export (src/telemetry.py)."""

import csv

import numpy as np

from src.telemetry import Telemetry, write_telemetry_csv


def _small_telemetry(n=3):
    return Telemetry(
        time_s=np.arange(n, dtype=float),
        grid_voltage_pu=np.ones(n),
        grid_available=np.ones(n, dtype=bool),
        p_load_w=np.full(n, 100.0),
        p_cmd_w=np.full(n, 100.0),
        p_target_w=np.full(n, 100.0),
        p_sst_w=np.full(n, 100.0),
        p_input_w=np.full(n, 103.0),
        p_loss_w=np.full(n, 3.0),
        e_dc_j=np.full(n, 6400.0),
        v_dc_v=np.full(n, 800.0),
        voltage_error_v=np.zeros(n),
        controller_integral_v_s=np.zeros(n),
        temperature_c=np.full(n, 25.0),
        operating_state=np.array(["RUNNING"] * n, dtype=object),
        derate_factor=np.ones(n),
        trip_active=np.zeros(n, dtype=bool),
        trip_reason=np.array([""] * n, dtype=object),
    )


def test_write_telemetry_csv_creates_file_with_header_and_rows(tmp_path):
    telemetry = _small_telemetry(n=5)
    csv_path = tmp_path / "out" / "telemetry.csv"

    write_telemetry_csv(telemetry, csv_path)

    assert csv_path.exists()
    with open(csv_path) as f:
        rows = list(csv.reader(f))

    assert rows[0][0] == "time_s"
    assert "operating_state" in rows[0]
    assert len(rows) == 1 + 5  # header + 5 data rows


def test_write_telemetry_csv_round_trips_values(tmp_path):
    telemetry = _small_telemetry(n=2)
    csv_path = tmp_path / "telemetry.csv"
    write_telemetry_csv(telemetry, csv_path)

    with open(csv_path) as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    assert float(rows[0]["v_dc_v"]) == 800.0
    assert rows[0]["operating_state"] == "RUNNING"
