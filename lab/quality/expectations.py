"""
Expectation suite đơn giản (không bắt buộc Great Expectations).

Sinh viên có thể thay bằng GE / pydantic / custom — miễn là có halt có kiểm soát.

Group 9 — Expectation mới (≥2):
  E7  no_bom_in_cleaned_chunks  : không chunk nào trong cleaned chứa BOM / zero-width
                                   (halt) — fails nếu rule R7 bị bỏ qua hoặc inject
                                   BOM vào pipeline với --skip-validate.
  E8  no_doc_id_dominance       : không doc_id nào chiếm > 80% tổng cleaned records
                                   (warn) — phát hiện data imbalance khi ingest lặp
                                   một nguồn.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

# Zero-width / BOM pattern (đồng bộ với cleaning_rules.py R7)
_INVISIBLE_CHARS = re.compile(
    r"[\ufeff\u200b\u200c\u200d\u00ad\u2060\ufffe]"
)

# E8: ngưỡng dominance
DOC_DOMINANCE_THRESHOLD = 0.80


@dataclass
class ExpectationResult:
    name: str
    passed: bool
    severity: str  # "warn" | "halt"
    detail: str


def run_expectations(cleaned_rows: List[Dict[str, Any]]) -> Tuple[List[ExpectationResult], bool]:
    """
    Trả về (results, should_halt).

    should_halt = True nếu có bất kỳ expectation severity halt nào fail.
    """
    results: List[ExpectationResult] = []

    # E1: có ít nhất 1 dòng sau clean
    ok = len(cleaned_rows) >= 1
    results.append(
        ExpectationResult(
            "min_one_row",
            ok,
            "halt",
            f"cleaned_rows={len(cleaned_rows)}",
        )
    )

    # E2: không doc_id rỗng
    bad_doc = [r for r in cleaned_rows if not (r.get("doc_id") or "").strip()]
    ok2 = len(bad_doc) == 0
    results.append(
        ExpectationResult(
            "no_empty_doc_id",
            ok2,
            "halt",
            f"empty_doc_id_count={len(bad_doc)}",
        )
    )

    # E3: policy refund không được chứa cửa sổ sai 14 ngày (sau khi đã fix)
    bad_refund = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "policy_refund_v4"
        and "14 ngày làm việc" in (r.get("chunk_text") or "")
    ]
    ok3 = len(bad_refund) == 0
    results.append(
        ExpectationResult(
            "refund_no_stale_14d_window",
            ok3,
            "halt",
            f"violations={len(bad_refund)}",
        )
    )

    # E4: chunk_text đủ dài
    short = [r for r in cleaned_rows if len((r.get("chunk_text") or "")) < 8]
    ok4 = len(short) == 0
    results.append(
        ExpectationResult(
            "chunk_min_length_8",
            ok4,
            "warn",
            f"short_chunks={len(short)}",
        )
    )

    # E5: effective_date đúng định dạng ISO sau clean (phát hiện parser lỏng)
    iso_bad = [
        r
        for r in cleaned_rows
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", (r.get("effective_date") or "").strip())
    ]
    ok5 = len(iso_bad) == 0
    results.append(
        ExpectationResult(
            "effective_date_iso_yyyy_mm_dd",
            ok5,
            "halt",
            f"non_iso_rows={len(iso_bad)}",
        )
    )

    # E6: không còn marker phép năm cũ 10 ngày trên doc HR (conflict version sau clean)
    bad_hr_annual = [
        r
        for r in cleaned_rows
        if r.get("doc_id") == "hr_leave_policy"
        and "10 ngày phép năm" in (r.get("chunk_text") or "")
    ]
    ok6 = len(bad_hr_annual) == 0
    results.append(
        ExpectationResult(
            "hr_leave_no_stale_10d_annual",
            ok6,
            "halt",
            f"violations={len(bad_hr_annual)}",
        )
    )

    # -----------------------------------------------------------------------
    # E7 (NEW — halt): không chunk nào trong cleaned chứa BOM hoặc zero-width chars.
    # Nếu rule R7 bị bỏ qua (skip hoặc bug), expectation này bắt lỗi lần cuối.
    # metric_impact: khi inject BOM vào CSV rồi chạy với --skip-validate,
    #   expectation[no_bom_in_cleaned_chunks] FAIL → ghi rõ trong log.
    #   Trên run chuẩn (CSV sạch): passed=True, violations=0.
    # -----------------------------------------------------------------------
    bom_rows = [
        r
        for r in cleaned_rows
        if _INVISIBLE_CHARS.search(r.get("chunk_text") or "")
    ]
    ok7 = len(bom_rows) == 0
    results.append(
        ExpectationResult(
            "no_bom_in_cleaned_chunks",
            ok7,
            "halt",
            f"bom_violations={len(bom_rows)}",
        )
    )

    # -----------------------------------------------------------------------
    # E8 (NEW — warn): không doc_id nào chiếm > 80% tổng cleaned records.
    # Phát hiện data imbalance: nếu pipeline bị inject lặp một nguồn (vd. 50 rows
    # sla_p1_2026 trong khi toàn bộ corpus chỉ có 6 rows) thì warn sớm.
    # metric_impact: inject 10 rows it_helpdesk_faq trùng doc_id → doc dominance
    #   it_helpdesk_faq vượt 80% → expectation[no_doc_id_dominance] WARN.
    #   Trên CSV mẫu 6 cleaned rows: max doc = policy_refund_v4 (2/6 ≈ 33%) → passed.
    # -----------------------------------------------------------------------
    if cleaned_rows:
        from collections import Counter
        doc_counts = Counter(r.get("doc_id", "") for r in cleaned_rows)
        total = len(cleaned_rows)
        dominant_doc, dominant_count = doc_counts.most_common(1)[0]
        ratio = dominant_count / total
        ok8 = ratio <= DOC_DOMINANCE_THRESHOLD
        results.append(
            ExpectationResult(
                "no_doc_id_dominance",
                ok8,
                "warn",
                f"dominant_doc={dominant_doc} ratio={ratio:.2f} threshold={DOC_DOMINANCE_THRESHOLD}",
            )
        )
    else:
        results.append(
            ExpectationResult(
                "no_doc_id_dominance",
                True,
                "warn",
                "no_cleaned_rows_to_check",
            )
        )

    halt = any(not r.passed and r.severity == "halt" for r in results)
    return results, halt
