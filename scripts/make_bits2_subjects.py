"""Create metadata/bits2_subjects.csv from Table 2 of the BITS-2 paper (D00b, user decision 10).

Source: docs/papers/BITS2_DataInBrief_2024.pdf (Nandi et al., Data in Brief 52 (2024) 109812), Table 2
"Volunteer details". Text is extracted with `pdftotext -layout` and parsed row by row; nothing is typed in.
`health_condition` and demographics are for ANALYSIS ONLY and must never be model inputs.
`base_hr_bpm` may later be used for relative-HR features (user decision 10).

Usage (from repo root):  python scripts/make_bits2_subjects.py
"""
import csv
import re
import subprocess
from pathlib import Path

PDF = Path("docs/papers/BITS2_DataInBrief_2024.pdf")
OUT = Path("metadata/bits2_subjects.csv")
ROW = re.compile(r"^\s*(\d{1,2})\s+(Male|Female)\s+([\d.]+)\s+([\d.]+)\s+(\d+)\s+(\d+)\s+(.+?)\s*$")


def main():
    if OUT.exists():
        raise FileExistsError(f"{OUT} exists; refusing to overwrite")
    text = subprocess.run(["pdftotext", "-layout", str(PDF), "-"], check=True,
                          capture_output=True, text=True).stdout
    table = text[text.index("Volunteer details."):text.index("Limitations")]
    rows = []
    for line in table.splitlines():
        m = ROW.match(line)
        if m:
            n = int(m.group(1))
            rows.append({
                "subject_number": n,
                "subject_id": f"BITS2_S{n:02d}",
                "raw_folder": f"user{n}",
                "gender": m.group(2),
                "height_cm": float(m.group(3)),
                "weight_kg": float(m.group(4)),
                "age_years": int(m.group(5)),
                "base_hr_bpm": int(m.group(6)),
                "health_condition": m.group(7),
                "use": "analysis_only_never_model_input (base_hr_bpm may feed relative-HR features)",
                "source": "Nandi et al. 2024, Data in Brief 52:109812, Table 2",
            })
    numbers = [r["subject_number"] for r in rows]
    assert numbers == list(range(1, 42)), f"expected subjects 1..41, got {numbers}"
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0]))
        w.writeheader()
        w.writerows(rows)
    print(f"wrote {OUT}: {len(rows)} subjects")


if __name__ == "__main__":
    main()
