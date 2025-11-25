from __future__ import annotations

import argparse
import asyncio
import csv
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import (
    BigInteger,
    Column,
    Float,
    MetaData,
    String,
    Table,
    Text,
    text,
)
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from domains.location.database.extensions import ensure_geospatial_extensions

from domains.location.jobs._csv_utils import (
    clean_float,
    clean_int,
    clean_str,
    resolve_csv_path,
)

DEFAULT_CSV_BASENAME = "keco_recycle_compensation_sites.csv"
BASE_DIR = Path(__file__).resolve().parent.parent
DEFAULT_CSV_PATH = resolve_csv_path(
    BASE_DIR,
    DEFAULT_CSV_BASENAME,
    search_keywords=("keco", "recycle"),
)
metadata = MetaData()

keco_table = Table(
    "location_keco_sites",
    metadata,
    Column("positn_sn", BigInteger, primary_key=True),
    Column("positn_nm", Text),
    Column("positn_rgn_nm", String(128)),
    Column("positn_lotno_addr", Text),
    Column("positn_rdnm_addr", Text),
    Column("positn_pstn_add_expln", Text),
    Column("positn_pstn_lat", Float),
    Column("positn_pstn_lot", Float),
    Column("positn_intdc_cn", Text),
    Column("positn_cnvnc_fclt_srvc_expln", Text),
    Column("prk_mthd_expln", Text),
    Column("mon_sals_hr_expln_cn", Text),
    Column("tues_sals_hr_expln_cn", Text),
    Column("wed_sals_hr_expln_cn", Text),
    Column("thur_sals_hr_expln_cn", Text),
    Column("fri_sals_hr_expln_cn", Text),
    Column("sat_sals_hr_expln_cn", Text),
    Column("sun_sals_hr_expln_cn", Text),
    Column("lhldy_sals_hr_expln_cn", Text),
    Column("lhldy_dyoff_cn", Text),
    Column("tmpr_lhldy_cn", Text),
    Column("dyoff_bgnde_cn", String(32)),
    Column("dyoff_enddt_cn", String(32)),
    Column("dyoff_rsn_expln", Text),
    Column("bsc_telno_cn", String(128)),
    Column("rprs_telno_cn", String(128)),
    Column("telno_expln", Text),
    Column("indiv_telno_cn", Text),
    Column("lnkg_hmpg_url_addr", Text),
    Column("indiv_rel_srch_list_cn", Text),
    Column("com_rel_srwrd_list_cn", Text),
    Column("clct_item_cn", Text),
    Column("etc_mttr_cn", Text),
    schema="location",
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Import KECO recycle compensation sites CSV into Postgres",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--csv-path",
        type=Path,
        default=DEFAULT_CSV_PATH,
        help="Path to KECO CSV file",
    )
    parser.add_argument(
        "--database-url",
        help="Override LOCATION_DATABASE_URL or DATABASE_URL env variables",
    )
    parser.add_argument("--batch-size", type=int, default=200, help="Rows per insert batch")
    return parser.parse_args()


def transform_row(row: dict[str, str]) -> dict[str, Any]:
    return {
        "positn_sn": clean_int(row.get("positnSn")),
        "positn_nm": clean_str(row.get("positnNm")),
        "positn_rgn_nm": clean_str(row.get("positnRgnNm")),
        "positn_lotno_addr": clean_str(row.get("positnLotnoAddr")),
        "positn_rdnm_addr": clean_str(row.get("positnRdnmAddr")),
        "positn_pstn_add_expln": clean_str(row.get("positnPstnAddExpln")),
        "positn_pstn_lat": clean_float(row.get("positnPstnLat")),
        "positn_pstn_lot": clean_float(row.get("positnPstnLot")),
        "positn_intdc_cn": clean_str(row.get("positnIntdcCn")),
        "positn_cnvnc_fclt_srvc_expln": clean_str(row.get("positnCnvncFcltSrvcExpln")),
        "prk_mthd_expln": clean_str(row.get("prkMthdExpln")),
        "mon_sals_hr_expln_cn": clean_str(row.get("monSalsHrExplnCn")),
        "tues_sals_hr_expln_cn": clean_str(row.get("tuesSalsHrExplnCn")),
        "wed_sals_hr_expln_cn": clean_str(row.get("wedSalsHrExplnCn")),
        "thur_sals_hr_expln_cn": clean_str(row.get("thurSalsHrExplnCn")),
        "fri_sals_hr_expln_cn": clean_str(row.get("friSalsHrExplnCn")),
        "sat_sals_hr_expln_cn": clean_str(row.get("satSalsHrExplnCn")),
        "sun_sals_hr_expln_cn": clean_str(row.get("sunSalsHrExplnCn")),
        "lhldy_sals_hr_expln_cn": clean_str(row.get("lhldySalsHrExplnCn")),
        "lhldy_dyoff_cn": clean_str(row.get("lhldyDyoffCn")),
        "tmpr_lhldy_cn": clean_str(row.get("tmprLhldyCn")),
        "dyoff_bgnde_cn": clean_str(row.get("dyoffBgndeCn")),
        "dyoff_enddt_cn": clean_str(row.get("dyoffEnddtCn")),
        "dyoff_rsn_expln": clean_str(row.get("dyoffRsnExpln")),
        "bsc_telno_cn": clean_str(row.get("bscTelnoCn")),
        "rprs_telno_cn": clean_str(row.get("rprsTelnoCn")),
        "telno_expln": clean_str(row.get("telnoExpln")),
        "indiv_telno_cn": clean_str(row.get("indivTelnoCn")),
        "lnkg_hmpg_url_addr": clean_str(row.get("lnkgHmpgUrlAddr")),
        "indiv_rel_srch_list_cn": clean_str(row.get("indivRelSrchListCn")),
        "com_rel_srwrd_list_cn": clean_str(row.get("comRelSrwrdListCn")),
        "clct_item_cn": clean_str(row.get("clctItemCn")),
        "etc_mttr_cn": clean_str(row.get("etcMttrCn")),
    }


async def ensure_schema(engine: AsyncEngine) -> None:
    await ensure_geospatial_extensions(engine)
    async with engine.begin() as conn:
        exists = await conn.scalar(
            text("SELECT 1 FROM information_schema.schemata " "WHERE schema_name = :schema_name"),
            {"schema_name": "location"},
        )
        if not exists:
            await conn.execute(text("CREATE SCHEMA IF NOT EXISTS location"))


async def ensure_table(engine: AsyncEngine) -> None:
    await ensure_schema(engine)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all, tables=[keco_table])


async def upsert_batch(engine: AsyncEngine, batch: list[dict[str, Any]]) -> None:
    if not batch:
        return
    stmt = insert(keco_table).values(batch)
    update_columns = {
        column.name: getattr(stmt.excluded, column.name)
        for column in keco_table.columns
        if column.name != "positn_sn"
    }
    async with engine.begin() as conn:
        await conn.execute(
            stmt.on_conflict_do_update(index_elements=[keco_table.c.positn_sn], set_=update_columns)
        )


def resolve_database_url(cli_value: str | None) -> str:
    if cli_value:
        return cli_value
    import os

    env_value = os.getenv("LOCATION_DATABASE_URL") or os.getenv("DATABASE_URL")
    if not env_value:
        raise SystemExit("Set LOCATION_DATABASE_URL or DATABASE_URL")
    return env_value


async def import_csv(engine: AsyncEngine, csv_path: Path, batch_size: int) -> int:
    total = 0
    pending: list[dict[str, Any]] = []
    with csv_path.open("r", encoding="utf-8-sig", newline="") as file_obj:
        reader: Iterable[dict[str, str]] = csv.DictReader(file_obj)
        for row in reader:
            mapped = transform_row(row)
            if mapped["positn_sn"] is None:
                continue
            pending.append(mapped)
            if len(pending) >= batch_size:
                await upsert_batch(engine, pending)
                total += len(pending)
                pending.clear()
    if pending:
        await upsert_batch(engine, pending)
        total += len(pending)
    return total


async def main() -> None:
    args = parse_args()
    csv_path = args.csv_path.resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV file not found: {csv_path}")

    database_url = resolve_database_url(args.database_url)
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)

    await ensure_table(engine)
    total_rows = await import_csv(engine, csv_path, args.batch_size)
    await engine.dispose()
    print(f"Imported {total_rows} KECO rows from {csv_path}")


if __name__ == "__main__":
    asyncio.run(main())
