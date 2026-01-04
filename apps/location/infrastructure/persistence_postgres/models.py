"""SQLAlchemy ORM Models."""

from __future__ import annotations

from sqlalchemy import BigInteger, Float, String, Text, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy Base."""

    pass


class NormalizedLocationSite(Base):
    """정규화된 위치 사이트 ORM 모델."""

    __tablename__ = "location_normalized_sites"
    __table_args__ = (
        UniqueConstraint("source", "source_pk", name="uq_location_normalized_source"),
        {"schema": "location"},
    )

    positn_sn: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    source: Mapped[str] = mapped_column(String(32), nullable=False)
    source_pk: Mapped[str] = mapped_column(String(128), nullable=False)
    positn_nm: Mapped[str | None] = mapped_column(Text)
    positn_rgn_nm: Mapped[str | None] = mapped_column(String(128))
    positn_lotno_addr: Mapped[str | None] = mapped_column(Text)
    positn_rdnm_addr: Mapped[str | None] = mapped_column(Text)
    positn_pstn_add_expln: Mapped[str | None] = mapped_column(Text)
    positn_pstn_lat: Mapped[float | None] = mapped_column(Float)
    positn_pstn_lot: Mapped[float | None] = mapped_column(Float)
    positn_intdc_cn: Mapped[str | None] = mapped_column(Text)
    positn_cnvnc_fclt_srvc_expln: Mapped[str | None] = mapped_column(Text)
    prk_mthd_expln: Mapped[str | None] = mapped_column(Text)
    mon_sals_hr_expln_cn: Mapped[str | None] = mapped_column(Text)
    tues_sals_hr_expln_cn: Mapped[str | None] = mapped_column(Text)
    wed_sals_hr_expln_cn: Mapped[str | None] = mapped_column(Text)
    thur_sals_hr_expln_cn: Mapped[str | None] = mapped_column(Text)
    fri_sals_hr_expln_cn: Mapped[str | None] = mapped_column(Text)
    sat_sals_hr_expln_cn: Mapped[str | None] = mapped_column(Text)
    sun_sals_hr_expln_cn: Mapped[str | None] = mapped_column(Text)
    lhldy_sals_hr_expln_cn: Mapped[str | None] = mapped_column(Text)
    lhldy_dyoff_cn: Mapped[str | None] = mapped_column(Text)
    tmpr_lhldy_cn: Mapped[str | None] = mapped_column(Text)
    dyoff_bgnde_cn: Mapped[str | None] = mapped_column(String(32))
    dyoff_enddt_cn: Mapped[str | None] = mapped_column(String(32))
    dyoff_rsn_expln: Mapped[str | None] = mapped_column(Text)
    bsc_telno_cn: Mapped[str | None] = mapped_column(String(128))
    rprs_telno_cn: Mapped[str | None] = mapped_column(String(128))
    telno_expln: Mapped[str | None] = mapped_column(Text)
    indiv_telno_cn: Mapped[str | None] = mapped_column(Text)
    lnkg_hmpg_url_addr: Mapped[str | None] = mapped_column(Text)
    indiv_rel_srch_list_cn: Mapped[str | None] = mapped_column(Text)
    com_rel_srwrd_list_cn: Mapped[str | None] = mapped_column(Text)
    clct_item_cn: Mapped[str | None] = mapped_column(Text)
    etc_mttr_cn: Mapped[str | None] = mapped_column(Text)
    source_metadata: Mapped[str | None] = mapped_column(Text)
