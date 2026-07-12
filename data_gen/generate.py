"""Synthetic data generator for the Remit Reconciliation Engine.

Generates 100% synthetic utility-billing entities:
  Account, Payment, Remit, UtilityCharge, CustCharge, AdjustmentAmt,
  Adjustments, plus an ExportRC file carrying the reported "R-C" difference.

Every recon scenario the engine must handle is injected on purpose
(duplicate dollar amounts, summary mismatches, misreported R-C, accounts
that fail every check) so the zero-out dedupe and manual-review paths are
demonstrable end to end.

All money is handled in integer cents internally and emitted as 2-dp dollars.

Usage:
  python data_gen/generate.py                 # fresh base build (batch B0001)
  python data_gen/generate.py --append        # append one new remit cycle
  python data_gen/generate.py --accounts 150  # base build size
"""

from __future__ import annotations

import argparse
import random
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

OUT_DIR = Path(__file__).resolve().parent / "output"

FIRST_NAMES = [
    "Ada", "Bram", "Celia", "Dorian", "Esme", "Farid", "Greta", "Hollis",
    "Imani", "Jasper", "Kaia", "Lionel", "Mira", "Nolan", "Odette", "Priya",
    "Quentin", "Rosa", "Silas", "Tamsin", "Ulric", "Vera", "Wendell", "Xiomara",
    "Yusuf", "Zelda", "Arlo", "Beatrix", "Cormac", "Delphine",
]
LAST_NAMES = [
    "Abernathy", "Boulware", "Castellano", "Dunmore", "Eastwick", "Fairbanks",
    "Goldwyn", "Hartsfield", "Ives", "Joubert", "Kessler", "Lindqvist",
    "Marchetti", "Northcott", "Okonkwo", "Pemberton", "Quintrell", "Rosewater",
    "Sablewood", "Thackeray", "Underhill", "Vasquez", "Winterbourne", "Xanthos",
    "Yarborough", "Zimmerle", "Ashgrove", "Blackwell", "Crowhurst", "Dovetail",
]
CITIES = [
    ("Milldale", "OH"), ("Harborview", "MI"), ("Cedar Bluff", "TN"),
    ("Fox Hollow", "PA"), ("Larkspur", "CO"), ("Gullport", "FL"),
    ("Stonebridge", "VA"), ("Windmere", "WI"), ("Oak Junction", "MO"),
    ("Pinehurst Flats", "NC"), ("Copper Ridge", "AZ"), ("Elm Grove", "IN"),
]
SERVICE_TYPES = ["Electric", "Gas", "Water", "Electric+Gas"]
PAYMENT_METHODS = ["ACH", "Card", "Check", "Lockbox"]
CHARGE_TYPES = ["Energy", "Delivery", "Base Fee", "Rider", "Tax Surcharge"]
ADJ_REASONS = ["LATE_FEE_WAIVER", "METER_CORRECTION", "GOODWILL_CREDIT",
               "RETURNED_PAYMENT_FEE", "BUDGET_TRUEUP", "SERVICE_CANCELLATION"]

# Scenario -> weight. Each scenario exists to exercise a specific recon path.
SCENARIOS = {
    "clean":           0.52,  # all checks pass, R-C = 0
    "dup_payment":     0.10,  # duplicated payment row -> zero-out fixes it
    "dup_charge":      0.05,  # duplicated utility charge row -> zero-out fixes it
    "dup_adjustment":  0.04,  # duplicated adjustment row -> zero-out fixes it
    "payment_short":   0.06,  # real underpayment, no dups -> manual review
    "charge_mismatch": 0.05,  # CustCharge summary disagrees with detail
    "adj_mismatch":    0.04,  # Adjustments summary disagrees with detail
    "rc_misreport":    0.05,  # sums fine but export reports a bogus R-C diff
    "known_diff":      0.04,  # remit short vs charges but correctly reported
    "total_fail":      0.03,  # fails every check
    "dup_unfixable":   0.02,  # dup + real shortfall: zero-out alone can't fix
}


def cents(lo: float, hi: float, rng: random.Random) -> int:
    return rng.randint(int(lo * 100), int(hi * 100))


def split_amount(total: int, n: int, rng: random.Random) -> list[int]:
    """Split `total` cents into n positive parts that sum exactly to total."""
    if n <= 1 or total <= n:
        return [total]
    cuts = sorted(rng.sample(range(1, total), n - 1))
    parts, prev = [], 0
    for c in cuts:
        parts.append(c - prev)
        prev = c
    parts.append(total - prev)
    return parts


class IdMinter:
    """Sequential, collision-free IDs continuing from any existing data."""

    def __init__(self, existing_max: dict[str, int]):
        self.counters = dict(existing_max)

    def mint(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}-{self.counters[prefix]:06d}"


def pick_scenario(rng: random.Random) -> str:
    names, weights = zip(*SCENARIOS.items())
    return rng.choices(names, weights=weights, k=1)[0]


def make_account(minter: IdMinter, rng: random.Random) -> dict:
    city, state = rng.choice(CITIES)
    return {
        "account_id": minter.mint("ACCT"),
        "customer_name": f"{rng.choice(FIRST_NAMES)} {rng.choice(LAST_NAMES)}",
        "service_type": rng.choice(SERVICE_TYPES),
        "city": city,
        "state": state,
        "enrolled_date": (date(2022, 1, 1)
                          + timedelta(days=rng.randint(0, 1200))).isoformat(),
    }


def generate_cycle(account: dict, batch_id: str, cycle_date: date,
                   scenario: str, minter: IdMinter, rng: random.Random) -> dict:
    """Generate one remit cycle for one account under a given scenario."""
    acct = account["account_id"]
    day = lambda spread: (cycle_date - timedelta(days=rng.randint(0, spread))).isoformat()

    # --- honest baseline ------------------------------------------------
    charges = [
        {"charge_id": minter.mint("CHG"), "account_id": acct, "batch_id": batch_id,
         "charge_date": day(25), "charge_type": rng.choice(CHARGE_TYPES),
         "charge_amount": cents(20, 400, rng)}
        for _ in range(rng.randint(1, 4))
    ]
    cust_charge_total = sum(c["charge_amount"] for c in charges)

    n_adj = rng.randint(0, 2)
    if scenario == "dup_adjustment" and n_adj == 0:
        n_adj = 1
    adjustments = []
    for _ in range(n_adj):
        amt = 0
        while amt == 0:
            amt = cents(-50, 50, rng)
        adjustments.append(
            {"adjustment_id": minter.mint("ADJ"), "account_id": acct,
             "batch_id": batch_id, "adj_date": day(20),
             "reason_code": rng.choice(ADJ_REASONS), "adjustment_amt": amt})
    # keep the remit comfortably positive
    adj_total = sum(a["adjustment_amt"] for a in adjustments)
    if cust_charge_total + adj_total < 1000:
        adjustments = []
        adj_total = 0

    adjustments_summary_total = adj_total          # what the Adjustments summary reports
    cust_charge_summary_total = cust_charge_total  # what the CustCharge summary reports
    remit_total = cust_charge_total + adj_total    # what actually got remitted
    reported_rc: int | None = 0                    # export's reported R-C difference

    # --- scenario mutations ----------------------------------------------
    note = ""
    if scenario == "charge_mismatch":
        delta = rng.choice([-1, 1]) * cents(5, 60, rng)
        cust_charge_summary_total += delta
        remit_total = cust_charge_summary_total + adjustments_summary_total
        note = "CustCharge summary drifted from charge detail"
    elif scenario == "adj_mismatch":
        delta = rng.choice([-1, 1]) * cents(3, 40, rng)
        adjustments_summary_total += delta
        remit_total = cust_charge_summary_total + adjustments_summary_total
        note = "Adjustments summary drifted from adjustment detail"
    elif scenario == "known_diff":
        short = cents(10, 80, rng)
        remit_total -= short
        reported_rc = short  # correctly disclosed on the export
        note = "Remit short vs charges; difference disclosed on export"
    elif scenario == "total_fail":
        remit_total += cents(40, 120, rng)  # remit no longer ties to summaries
        note = "Every check seeded to fail"

    payments = [
        {"payment_id": minter.mint("PMT"), "account_id": acct, "batch_id": batch_id,
         "payment_date": day(12), "payment_method": rng.choice(PAYMENT_METHODS),
         "payment_amount": part}
        for part in split_amount(remit_total, rng.randint(1, 3), rng)
    ]

    if scenario in ("payment_short", "total_fail", "dup_unfixable"):
        biggest = max(payments, key=lambda p: p["payment_amount"])
        delta = cents(5, 50, rng)
        biggest["payment_amount"] = max(biggest["payment_amount"] - delta, 100)
        note = note or "Payment detail short of remit; no duplicates to zero out"

    if scenario in ("dup_payment", "dup_unfixable"):
        src = rng.choice(payments)
        dup = dict(src, payment_id=minter.mint("PMT"))
        payments.append(dup)
        note = note or "Duplicate payment row inflates SUM(Payment)"
    if scenario == "dup_charge":
        src = rng.choice(charges)
        charges.append(dict(src, charge_id=minter.mint("CHG")))
        note = "Duplicate charge row inflates SUM(UtilityCharge)"
    if scenario == "dup_adjustment":
        src = rng.choice(adjustments)
        adjustments.append(dict(src, adjustment_id=minter.mint("ADJ")))
        note = "Duplicate adjustment row inflates SUM(AdjustmentAmt)"

    if scenario == "rc_misreport":
        reported_rc = rng.choice([-1, 1]) * cents(1, 15, rng)
        note = "Export reports a phantom R-C difference"
    elif scenario == "total_fail":
        reported_rc = 0  # real difference exists but export claims none

    return {
        "payments": payments,
        "charges": charges,
        "adjustment_amts": adjustments,
        "remit": {"remit_id": minter.mint("RMT"), "account_id": acct,
                  "batch_id": batch_id, "remit_date": cycle_date.isoformat(),
                  "remit_amount": remit_total},
        "cust_charge": {"cust_charge_id": minter.mint("CCH"), "account_id": acct,
                        "batch_id": batch_id,
                        "cust_charge_amount": cust_charge_summary_total},
        "adjustments": {"adjustments_id": minter.mint("ADS"), "account_id": acct,
                        "batch_id": batch_id,
                        "adjustments_amount": adjustments_summary_total},
        "export_rc": {"export_id": minter.mint("EXP"), "account_id": acct,
                      "batch_id": batch_id, "export_date": cycle_date.isoformat(),
                      "reported_rc_difference": reported_rc},
        "scenario": {"account_id": acct, "batch_id": batch_id,
                     "scenario": scenario, "note": note},
    }


TABLES = ["accounts", "payments", "remits", "utility_charges", "cust_charges",
          "adjustment_amts", "adjustments", "export_rc", "_scenarios"]
MONEY_COLS = {
    "payments": ["payment_amount"],
    "remits": ["remit_amount"],
    "utility_charges": ["charge_amount"],
    "cust_charges": ["cust_charge_amount"],
    "adjustment_amts": ["adjustment_amt"],
    "adjustments": ["adjustments_amount"],
    "export_rc": ["reported_rc_difference"],
}


def load_existing() -> dict[str, pd.DataFrame]:
    frames = {}
    for t in TABLES:
        f = OUT_DIR / f"{t}.csv"
        if f.exists():
            frames[t] = pd.read_csv(f)
    return frames


def existing_id_maxima(frames: dict[str, pd.DataFrame]) -> dict[str, int]:
    maxima: dict[str, int] = {}
    id_cols = {"accounts": "account_id", "payments": "payment_id",
               "remits": "remit_id", "utility_charges": "charge_id",
               "cust_charges": "cust_charge_id", "adjustment_amts": "adjustment_id",
               "adjustments": "adjustments_id", "export_rc": "export_id"}
    for table, col in id_cols.items():
        if table in frames and len(frames[table]):
            nums = frames[table][col].str.split("-").str[-1].astype(int)
            prefix = frames[table][col].iloc[0].split("-")[0]
            maxima[prefix] = int(nums.max())
    return maxima


def run(n_accounts: int, append: bool, seed: int | None) -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    existing = load_existing() if append else {}

    if append and "accounts" not in existing:
        sys.exit("--append requires an existing base build in data_gen/output/")

    if append:
        prev_batches = sorted(existing["remits"]["batch_id"].unique())
        batch_num = int(prev_batches[-1][1:]) + 1
        rng = random.Random(seed if seed is not None else batch_num * 7919)
    else:
        batch_num = 1
        rng = random.Random(seed if seed is not None else 42)
    batch_id = f"B{batch_num:04d}"
    cycle_date = date(2026, 1, 15) + timedelta(days=30 * (batch_num - 1))

    minter = IdMinter(existing_id_maxima(existing))

    if append:
        base_accounts = existing["accounts"].to_dict("records")
        k = min(len(base_accounts), rng.randint(25, 35))
        cycle_accounts = rng.sample(base_accounts, k)
        new_accounts = [make_account(minter, rng) for _ in range(rng.randint(2, 4))]
        cycle_accounts += new_accounts
        all_accounts = base_accounts + new_accounts
    else:
        all_accounts = [make_account(minter, rng) for _ in range(n_accounts)]
        cycle_accounts = all_accounts

    rows: dict[str, list] = {t: [] for t in TABLES}
    rows["accounts"] = all_accounts
    for acct in cycle_accounts:
        scenario = pick_scenario(rng)
        cycle = generate_cycle(acct, batch_id, cycle_date, scenario, minter, rng)
        rows["payments"] += cycle["payments"]
        rows["utility_charges"] += cycle["charges"]
        rows["adjustment_amts"] += cycle["adjustment_amts"]
        rows["remits"].append(cycle["remit"])
        rows["cust_charges"].append(cycle["cust_charge"])
        rows["adjustments"].append(cycle["adjustments"])
        rows["export_rc"].append(cycle["export_rc"])
        rows["_scenarios"].append(cycle["scenario"])

    generated_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
    frames: dict[str, pd.DataFrame] = {}
    for table in TABLES:
        df = pd.DataFrame(rows[table])
        if table != "accounts":
            df["generated_at"] = generated_at
        for col in MONEY_COLS.get(table, []):
            df[col] = (df[col] / 100).round(2)
        if append and table in existing and table != "accounts":
            df = pd.concat([existing[table], df], ignore_index=True)
        frames[table] = df

    for table, df in frames.items():
        df.to_csv(OUT_DIR / f"{table}.csv", index=False)
        if not table.startswith("_"):
            df.to_parquet(OUT_DIR / f"{table}.parquet", index=False)

    scen_counts = (pd.DataFrame(rows["_scenarios"])["scenario"]
                   .value_counts().sort_index())
    print(f"=== batch {batch_id} generated ({'append' if append else 'base build'}) ===")
    print(f"cycle date: {cycle_date}  |  accounts in cycle: {len(cycle_accounts)}"
          f"  |  total accounts: {len(all_accounts)}")
    print("\nscenario mix (this batch):")
    for name, count in scen_counts.items():
        print(f"  {name:<16} {count}")
    print("\nrow counts (cumulative):")
    for table in TABLES:
        print(f"  {table:<16} {len(frames[table]):>6}")
    print(f"\nwrote CSV + Parquet to {OUT_DIR}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--accounts", type=int, default=120,
                    help="number of accounts for a base build")
    ap.add_argument("--append", action="store_true",
                    help="append one new remit cycle to the existing data")
    ap.add_argument("--seed", type=int, default=None,
                    help="override the deterministic RNG seed")
    args = ap.parse_args()
    run(args.accounts, args.append, args.seed)
