"""
Cleaning rules — raw export → cleaned rows + quarantine.

Baseline gồm các failure mode mở rộng (allowlist doc_id, parse ngày, HR stale version).
Sinh viên thêm ≥3 rule mới: mỗi rule phải ghi `metric_impact` (xem README — chống trivial).

Group 9 — Rule mới:
  R7  bom_or_invisible_chars  : quarantine chunk_text chứa BOM / zero-width chars
                                → metric_impact: khi inject BOM vào CSV,
                                  quarantine_records tăng thêm N (đo trong inject run).
  R8  sla_value_sanity        : quarantine sla_p1_2026 chunk có SLA phản hồi > 120 phút
                                trong text (phát hiện giá trị corrupt / đơn vị sai).
                                → metric_impact: inject SLA "900 phút" → quarantine +1.
  R9  min_word_count_5        : quarantine chunk < 5 từ (loại stub / test record quá ngắn)
                                → metric_impact: row 5 gốc (empty text) đã bị rule 4 bắt;
                                  khi inject stub "OK." → quarantine +1 nhờ R9.
"""

from __future__ import annotations

import csv
import hashlib
import re
from pathlib import Path
from typing import Any, Dict, List, Tuple

# Khớp export hợp lệ trong lab (mở rộng khi nhóm thêm doc mới — phải đồng bộ contract).
ALLOWED_DOC_IDS = frozenset(
    {
        "policy_refund_v4",
        "sla_p1_2026",
        "it_helpdesk_faq",
        "hr_leave_policy",
    }
)

_ISO_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
_DMY_SLASH = re.compile(r"^(\d{2})/(\d{2})/(\d{4})$")

# R8: pattern phát hiện SLA phản hồi > 120 phút trong text (bắt số + "phút")
_SLA_MINUTES_PATTERN = re.compile(r"(\d+)\s*phút", re.IGNORECASE)
SLA_MAX_RESPONSE_MINUTES = 120  # giới hạn hợp lý theo contract

# R7: các ký tự vô hình / BOM phổ biến
_INVISIBLE_CHARS = re.compile(
    r"[\ufeff\u200b\u200c\u200d\u00ad\u2060\ufffe]"
)

# R9: số từ tối thiểu sau khi strip
MIN_WORD_COUNT = 5


def _norm_text(s: str) -> str:
    return " ".join((s or "").strip().split()).lower()


def _stable_chunk_id(doc_id: str, chunk_text: str, seq: int) -> str:
    h = hashlib.sha256(f"{doc_id}|{chunk_text}|{seq}".encode("utf-8")).hexdigest()[:16]
    return f"{doc_id}_{seq}_{h}"


def _normalize_effective_date(raw: str) -> Tuple[str, str]:
    """
    Trả về (iso_date, error_reason).
    iso_date rỗng nếu không parse được.
    """
    s = (raw or "").strip()
    if not s:
        return "", "empty_effective_date"
    if _ISO_DATE.match(s):
        return s, ""
    m = _DMY_SLASH.match(s)
    if m:
        dd, mm, yyyy = m.group(1), m.group(2), m.group(3)
        return f"{yyyy}-{mm}-{dd}", ""
    return "", "invalid_effective_date_format"


# ---------------------------------------------------------------------------
# R7 helper — BOM / zero-width character detection
# ---------------------------------------------------------------------------
def _has_invisible_chars(text: str) -> bool:
    """
    Rule R7: Trả về True nếu text chứa BOM (\\ufeff) hoặc các ký tự zero-width
    phổ biến. Những ký tự này không hiển thị khi đọc bằng mắt nhưng làm hỏng
    embedding (vector bị lệch) và matching keyword.

    metric_impact: inject 1 row có BOM prefix → quarantine_records tăng +1;
    run chuẩn (CSV sạch) → không thay đổi quarantine count.
    """
    return bool(_INVISIBLE_CHARS.search(text))


# ---------------------------------------------------------------------------
# R8 helper — SLA value sanity (sla_p1_2026 specific)
# ---------------------------------------------------------------------------
def _sla_value_out_of_range(doc_id: str, text: str) -> bool:
    """
    Rule R8: Với doc sla_p1_2026, quét tất cả số phút được đề cập trong chunk_text.
    Nếu bất kỳ giá trị nào > SLA_MAX_RESPONSE_MINUTES (120 phút) → quarantine.

    Lý do: export SLA từ hệ cũ đôi khi ghi "900 phút" thay vì "15 phút" hoặc
    nhầm đơn vị giờ→phút. Rule này phát hiện corruption đơn vị sớm.

    metric_impact: inject row sla_p1_2026 với "900 phút" → quarantine_records +1;
    baseline CSV (15 phút, 4 giờ) → không bị quarantine vì chỉ "15 phút" xuất hiện.
    """
    if doc_id != "sla_p1_2026":
        return False
    matches = _SLA_MINUTES_PATTERN.findall(text)
    for m in matches:
        try:
            if int(m) > SLA_MAX_RESPONSE_MINUTES:
                return True
        except ValueError:
            pass
    return False


# ---------------------------------------------------------------------------
# R9 helper — Minimum word count
# ---------------------------------------------------------------------------
def _too_few_words(text: str) -> bool:
    """
    Rule R9: Quarantine chunk có < MIN_WORD_COUNT (5) từ sau khi strip.
    Loại bỏ stub / test record / placeholder quá ngắn mà rule 4 (empty text)
    chưa bắt được.

    metric_impact: inject stub "OK." (1 từ) → quarantine_records +1;
    row 5 trong baseline CSV đã bị rule 4 bắt (empty text) → R9 không overlap.
    """
    words = (text or "").strip().split()
    return len(words) < MIN_WORD_COUNT


def load_raw_csv(path: Path) -> List[Dict[str, str]]:
    rows: List[Dict[str, str]] = []
    with path.open(encoding="utf-8-sig", newline="") as f:  # utf-8-sig tự bóc BOM cấp file
        reader = csv.DictReader(f)
        for r in reader:
            rows.append({k: (v or "").strip() for k, v in r.items()})
    return rows


def clean_rows(
    rows: List[Dict[str, str]],
    *,
    apply_refund_window_fix: bool = True,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    """
    Trả về (cleaned, quarantine).

    Baseline (mở rộng theo narrative Day 10):
    1) Quarantine: doc_id không thuộc allowlist (export lạ / catalog sai).
    2) Chuẩn hoá effective_date sang YYYY-MM-DD; quarantine nếu không parse được.
    3) Quarantine: chunk hr_leave_policy có effective_date < 2026-01-01 (bản HR cũ / conflict version).
    4) Quarantine: chunk_text rỗng hoặc effective_date rỗng sau chuẩn hoá.
    5) Loại trùng nội dung chunk_text (giữ bản đầu).
    6) Fix stale refund: policy_refund_v4 chứa '14 ngày làm việc' → 7 ngày.

    Group 9 — Rule mới (≥3):
    R7) Quarantine: chunk_text chứa BOM / zero-width chars (gây lệch embedding).
    R8) Quarantine: sla_p1_2026 chunk có số phút > 120 (SLA corrupt / đơn vị sai).
    R9) Quarantine: chunk_text < 5 từ (stub / test record quá ngắn).
    """
    quarantine: List[Dict[str, Any]] = []
    seen_text: set[str] = set()
    cleaned: List[Dict[str, Any]] = []
    seq = 0

    for raw in rows:
        doc_id = raw.get("doc_id", "")
        text = raw.get("chunk_text", "")
        eff_raw = raw.get("effective_date", "")
        exported_at = raw.get("exported_at", "")

        # --- Baseline rule 1: allowlist doc_id ---
        if doc_id not in ALLOWED_DOC_IDS:
            quarantine.append({**raw, "reason": "unknown_doc_id"})
            continue

        # --- Baseline rule 2: normalize effective_date ---
        eff_norm, eff_err = _normalize_effective_date(eff_raw)
        if eff_err == "empty_effective_date":
            quarantine.append({**raw, "reason": "missing_effective_date"})
            continue
        if eff_err == "invalid_effective_date_format":
            quarantine.append({**raw, "reason": eff_err, "effective_date_raw": eff_raw})
            continue

        # --- Baseline rule 3: HR stale version ---
        if doc_id == "hr_leave_policy" and eff_norm < "2026-01-01":
            quarantine.append(
                {
                    **raw,
                    "reason": "stale_hr_policy_effective_date",
                    "effective_date_normalized": eff_norm,
                }
            )
            continue

        # --- Baseline rule 4: empty text ---
        if not text:
            quarantine.append({**raw, "reason": "missing_chunk_text"})
            continue

        # --- Rule R7 (NEW): BOM / zero-width chars in chunk_text ---
        if _has_invisible_chars(text):
            quarantine.append(
                {
                    **raw,
                    "reason": "bom_or_invisible_chars",
                    "detail": "chunk_text contains BOM or zero-width characters",
                }
            )
            continue

        # --- Rule R8 (NEW): SLA value sanity for sla_p1_2026 ---
        if _sla_value_out_of_range(doc_id, text):
            quarantine.append(
                {
                    **raw,
                    "reason": "sla_value_out_of_range",
                    "detail": f"sla minutes > {SLA_MAX_RESPONSE_MINUTES} detected in text",
                }
            )
            continue

        # --- Rule R9 (NEW): Minimum word count (5 words) ---
        if _too_few_words(text):
            quarantine.append(
                {
                    **raw,
                    "reason": "too_few_words",
                    "detail": f"chunk_text has fewer than {MIN_WORD_COUNT} words",
                }
            )
            continue

        # --- Baseline rule 5: dedupe by normalized text ---
        key = _norm_text(text)
        if key in seen_text:
            quarantine.append({**raw, "reason": "duplicate_chunk_text"})
            continue
        seen_text.add(key)

        # --- Baseline rule 6: fix stale refund window 14→7 ---
        fixed_text = text
        if apply_refund_window_fix and doc_id == "policy_refund_v4":
            if "14 ngày làm việc" in fixed_text:
                fixed_text = fixed_text.replace(
                    "14 ngày làm việc",
                    "7 ngày làm việc",
                )
                fixed_text += " [cleaned: stale_refund_window]"

        seq += 1
        cleaned.append(
            {
                "chunk_id": _stable_chunk_id(doc_id, fixed_text, seq),
                "doc_id": doc_id,
                "chunk_text": fixed_text,
                "effective_date": eff_norm,
                "exported_at": exported_at or "",
            }
        )

    return cleaned, quarantine


def write_cleaned_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at\n", encoding="utf-8")
        return
    fieldnames = ["chunk_id", "doc_id", "chunk_text", "effective_date", "exported_at"]
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fieldnames})


def write_quarantine_csv(path: Path, rows: List[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("chunk_id,doc_id,chunk_text,effective_date,exported_at,reason\n", encoding="utf-8")
        return
    keys: List[str] = []
    seen_k: set[str] = set()
    for r in rows:
        for k in r.keys():
            if k not in seen_k:
                seen_k.add(k)
                keys.append(k)
    with path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys, extrasaction="ignore", restval="")
        w.writeheader()
        for r in rows:
            w.writerow(r)
