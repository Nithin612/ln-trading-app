"""CAMS CAS (Consolidated Account Statement) PDF parser — Phase 11.

Two entry points:
  parse_cas_text(text)  — parses pre-extracted text; useful for unit tests.
  parse_cas_pdf(bytes)  — opens PDF with pdfplumber, extracts text, delegates.

CAMS CAS format (typical):
  - Statement header with investor name, PAN, period
  - AMC sections separated by lines of dashes or the AMC name on its own line
  - Within each AMC: "Folio No.: XXXX / 0" then scheme blocks
  - Each scheme block ends with:
      Closing Balance: (or similar)
        Units: X.XXXX
        NAV (dd-Mon-yyyy): X.XXXX
        Valuation (INR): X,XXX.XX
"""

from __future__ import annotations

import io
import re
from dataclasses import dataclass, field
from datetime import date


# ── Data classes ──────────────────────────────────────────────────────────────

@dataclass
class CASHeader:
    investor_name: str | None = None
    pan: str | None = None
    statement_date: date | None = None  # parsed from "Period: dd-Mon-yyyy To dd-Mon-yyyy"


@dataclass
class CASHolding:
    amc_name: str
    scheme_name: str
    folio_number: str
    isin: str | None
    units: str           # keep as string; caller converts to Decimal
    nav: str
    current_value: str
    as_of_date: date | None = None


# ── Regex helpers ─────────────────────────────────────────────────────────────

_RE_PAN = re.compile(r"\bPAN\s*[:\-]\s*([A-Z]{5}[0-9]{4}[A-Z])\b")
_RE_FOLIO = re.compile(r"Folio\s*(?:No\.?|Number)\s*[:\-]?\s*([\w\d/\- ]+?)(?:\s+PAN|\s+KYC|\s*$)", re.IGNORECASE)
_RE_ISIN = re.compile(r"\bISIN\s*[:\-]\s*([A-Z]{2}[A-Z0-9]{10})\b", re.IGNORECASE)
_RE_UNITS = re.compile(r"(?:Closing\s+)?Units?\s*[:\-]\s*([\d,]+\.?\d*)", re.IGNORECASE)
_RE_NAV = re.compile(
    r"NAV\s*(?:\([^)]*\))?\s*[:\-]?\s*[₹Rs\.]*\s*([\d,]+\.?\d*)", re.IGNORECASE
)
_RE_VALUE = re.compile(
    r"(?:Valuation|Value|Market\s+Value)\s*(?:\([^)]*\))?\s*[:\-]\s*[₹Rs\.]*\s*([\d,]+\.?\d*)",
    re.IGNORECASE,
)
_RE_DATE = re.compile(r"\b(\d{1,2}[-/]\w{3}[-/]\d{4}|\d{2}[-/]\d{2}[-/]\d{4})\b")
_RE_PERIOD = re.compile(
    r"Period\s*[:\-]\s*(\d{2}[-/]\w{3}[-/]\d{4})\s+To\s+(\d{2}[-/]\w{3}[-/]\d{4})",
    re.IGNORECASE,
)

_KNOWN_AMC_KEYWORDS = (
    "mutual fund", "asset management", "mf", "amc", "trustee",
)

# Lines that look like section dividers or noise — skip them as AMC candidates
_SKIP_LINE_RE = re.compile(
    r"^\s*(?:[-=*#|]+|page\s+\d+|folio|isin|units|nav|closing|opening|"
    r"valuation|transaction|date|balance|statement|period|consolidated|"
    r"account|investor|pan|kyc|nominee|mobile|email|address)\b",
    re.IGNORECASE,
)


def _clean(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def _parse_date(s: str) -> date | None:
    """Try parsing common Indian date formats."""
    s = s.strip()
    formats = ("%d-%b-%Y", "%d/%b/%Y", "%d-%m-%Y", "%d/%m/%Y", "%d-%b-%y", "%d/%b/%y")
    for fmt in formats:
        try:
            from datetime import datetime
            return datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def _strip_commas(s: str) -> str:
    return s.replace(",", "")


# ── Main parser ───────────────────────────────────────────────────────────────

def parse_cas_text(text: str) -> tuple[CASHeader, list[CASHolding]]:
    """Parse CAMS CAS text into structured holdings.

    Tolerant of format variations across CAMS statement versions.
    Returns (header, holdings) where holdings may be empty if parsing fails.
    """
    lines = [_clean(ln) for ln in text.splitlines() if _clean(ln)]
    header = _extract_header(lines)
    holdings = _extract_holdings(lines)
    return header, holdings


def parse_cas_pdf(pdf_bytes: bytes) -> tuple[CASHeader, list[CASHolding]]:
    """Open PDF with pdfplumber, extract text, then parse."""
    import pdfplumber  # deferred import — not needed for unit tests

    with pdfplumber.open(io.BytesIO(pdf_bytes)) as pdf:
        pages_text = []
        for page in pdf.pages:
            t = page.extract_text()
            if t:
                pages_text.append(t)
    full_text = "\n".join(pages_text)
    return parse_cas_text(full_text)


# ── Header extraction ──────────────────────────────────────────────────────────

def _extract_header(lines: list[str]) -> CASHeader:
    header = CASHeader()
    for line in lines[:40]:  # header info is near the top
        m = _RE_PAN.search(line)
        if m and not header.pan:
            header.pan = m.group(1)

        # Investor name often appears after "Name:" or as first non-header line
        if re.search(r"^Name\s*[:\-]", line, re.IGNORECASE):
            header.investor_name = re.sub(r"^Name\s*[:\-]\s*", "", line, flags=re.IGNORECASE)

        m2 = _RE_PERIOD.search(line)
        if m2:
            # Use the "To" date as the statement date
            header.statement_date = _parse_date(m2.group(2))

    return header


# ── Holdings extraction ────────────────────────────────────────────────────────

def _has_complete_data(lines: list[str]) -> bool:
    """Return True if lines contain units + NAV + value."""
    text = " ".join(lines)
    return bool(_RE_UNITS.search(text) and _RE_NAV.search(text) and _RE_VALUE.search(text))


def _flush_scheme(
    holdings: list[CASHolding],
    scheme_lines: list[str],
    amc: str,
    scheme: str,
    folio: str,
    isin: str | None,
) -> None:
    """Parse accumulated scheme lines and append holding if successful."""
    h = _parse_scheme_block(scheme_lines, amc, scheme, folio, isin)
    if h:
        holdings.append(h)


def _extract_holdings(lines: list[str]) -> list[CASHolding]:
    holdings: list[CASHolding] = []
    current_amc: str = "Unknown AMC"
    current_folio: str = ""
    current_scheme: str = ""
    current_isin: str | None = None
    scheme_lines: list[str] = []

    for line in lines:
        # ── Detect AMC name ───────────────────────────────────────────────────
        if (
            any(kw in line.lower() for kw in _KNOWN_AMC_KEYWORDS)
            and not _SKIP_LINE_RE.match(line)
            and len(line) < 120
        ):
            if current_scheme:
                _flush_scheme(holdings, scheme_lines, current_amc, current_scheme, current_folio, current_isin)
                current_scheme = ""
                current_isin = None
                scheme_lines = []
            current_amc = line
            continue

        # ── Detect folio number ───────────────────────────────────────────────
        m_folio = _RE_FOLIO.match(line)
        if m_folio:
            if current_scheme:
                _flush_scheme(holdings, scheme_lines, current_amc, current_scheme, current_folio, current_isin)
                current_scheme = ""
                current_isin = None
                scheme_lines = []
            current_folio = _clean(m_folio.group(1).split("/")[0])
            continue

        # ── Detect ISIN ───────────────────────────────────────────────────────
        m_isin = _RE_ISIN.search(line)
        if m_isin:
            if not current_scheme:
                # ISIN before scheme name — store for later
                current_isin = m_isin.group(1).upper()
            else:
                # ISIN belonging to current scheme
                current_isin = m_isin.group(1).upper()
                scheme_lines.append(line)
            continue

        # ── Detect scheme name ────────────────────────────────────────────────
        if (
            current_folio
            and _looks_like_scheme_name(line)
            and not _RE_FOLIO.match(line)
        ):
            # Before starting a new scheme, flush the previous one IF it already
            # has complete data (units + NAV + value).  If not, keep accumulating.
            if current_scheme and _has_complete_data(scheme_lines):
                _flush_scheme(holdings, scheme_lines, current_amc, current_scheme, current_folio, current_isin)
                current_scheme = ""
                current_isin = None
                scheme_lines = []
            if not current_scheme:
                current_scheme = line
                scheme_lines = []
                continue
            # else: two scheme-name-like lines in a row — treat second as data
        elif current_scheme:
            scheme_lines.append(line)
            # Auto-flush when we have complete data and the block looks closed
            # (i.e., we've seen "valuation" which typically ends the block)
            if _RE_VALUE.search(line) and _has_complete_data(scheme_lines):
                _flush_scheme(holdings, scheme_lines, current_amc, current_scheme, current_folio, current_isin)
                current_scheme = ""
                current_isin = None
                scheme_lines = []

    # Flush trailing scheme
    if current_scheme:
        _flush_scheme(holdings, scheme_lines, current_amc, current_scheme, current_folio, current_isin)

    return holdings


def _looks_like_scheme_name(line: str) -> bool:
    """Heuristic: a scheme name line is typically 10-200 chars, mixed case,
    contains fund-related keywords, and doesn't look like a numeric value line."""
    if len(line) < 8 or len(line) > 250:
        return False
    if re.match(r"^\d", line):  # starts with digit → likely numeric data
        return False
    if _SKIP_LINE_RE.match(line):
        return False
    keywords = ("fund", "growth", "dividend", "option", "plan", "direct", "regular",
                "flexi", "cap", "equity", "debt", "liquid", "balanced", "hybrid",
                "index", "gilt", "income", "bluechip", "small", "mid", "large",
                "multi", "opportunity", "value", "focussed", "focused", "arbitrage",
                "overnight", "money market", "short duration", "long duration")
    lower = line.lower()
    return any(kw in lower for kw in keywords)


def _parse_scheme_block(
    lines: list[str],
    amc_name: str,
    scheme_name: str,
    folio_number: str,
    isin: str | None,
) -> CASHolding | None:
    """Extract units/NAV/value from the lines of a scheme block."""
    text = " ".join(lines)

    m_units = _RE_UNITS.search(text)
    m_nav = _RE_NAV.search(text)
    m_value = _RE_VALUE.search(text)

    if not (m_units and m_nav and m_value):
        return None

    units_str = _strip_commas(m_units.group(1))
    nav_str = _strip_commas(m_nav.group(1))
    value_str = _strip_commas(m_value.group(1))

    # Sanity: must be parseable as floats
    try:
        float(units_str)
        float(nav_str)
        float(value_str)
    except ValueError:
        return None

    # Extract as_of_date from NAV line if present
    as_of_date: date | None = None
    nav_line_m = re.search(
        r"NAV\s*\(([^)]+)\)", text, re.IGNORECASE
    )
    if nav_line_m:
        as_of_date = _parse_date(nav_line_m.group(1))

    return CASHolding(
        amc_name=_clean(amc_name),
        scheme_name=_clean(scheme_name),
        folio_number=_clean(folio_number),
        isin=isin,
        units=units_str,
        nav=nav_str,
        current_value=value_str,
        as_of_date=as_of_date,
    )
