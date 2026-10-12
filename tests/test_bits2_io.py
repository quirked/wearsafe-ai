"""Parser tests on small synthetic BITS-2-style CSV text (no raw data needed)."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
from wearsafe.bits2_io import parse_bytes, parse_name, rounding_step, sig_digits  # noqa: E402

SAMPLE = (
    "﻿t,x,y,z,a,\r\n"
    "1.82E+11,0.1,0.2,0.3,3,acc\r\n"
    "1.82E+11,0.4,0.5,0.6,3,acc\r\n"
    "t,x,y,z,a,\r\n"
    "1.82E+11,-9.8,0.1,0.2,3,acg\r\n"
    "1.83E+11,100,-1,hrt,,\r\n"
    "t,bpm,a,,,\r\n"
    "1.84E+11,101,3,hrt,,\r\n"
    ",,,,,\r\n"
    "1.85E+11,,,hrt,,\r\n"
    "5.85E+14,-9.0,-3.3,2.4,3,\r\n"
)


def test_parse_streams_and_quirks():
    f = parse_bytes(SAMPLE.encode("utf-8"))
    assert f.bom and f.crlf and not f.lone_cr
    assert len(f.streams["acc"]) == 2 and len(f.streams["acg"]) == 1
    assert f.streams["hrt"]["bpm"].tolist() == [100.0, 101.0]
    assert f.streams["hrt"]["status"].tolist() == ["-1", "3"]
    assert f.inner_headers == 2          # one IMU header, one HR header
    assert f.blank_rows == 1
    assert len(f.malformed) == 2         # HR row without bpm, IMU row without sensor tag
    assert f.block_order == "acc acg hrt"
    assert f.streams["acc"]["t_raw"].tolist() == ["1.82E+11", "1.82E+11"]


def test_lone_cr_line_endings():
    f = parse_bytes("t,x,y,z,a,\r1.0E+11,1,2,3,3,acc\r2.0E+11,1,2,3,3,acc\r".encode())
    assert f.lone_cr and len(f.streams["acc"]) == 2


def test_sig_digits_and_step():
    assert sig_digits("1.82E+11") == 3
    assert sig_digits("5E+14") == 1
    assert sig_digits("53000000000000") == 2
    assert rounding_step("1.82E+11") == pytest.approx(1e9)
    assert rounding_step("2.92E+12") == pytest.approx(1e10)


def test_parse_name():
    assert parse_name("user31_.fall1.csv") == (31, "fall", 1, True)
    assert parse_name("user7_adl16.csv") == (7, "adl", 16, False)
    assert parse_name("readme.txt") is None
