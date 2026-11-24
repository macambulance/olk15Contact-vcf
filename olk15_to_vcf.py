#!/usr/bin/env python3
"""Convert Outlook for Mac .olk15Contact files to vCard (.vcf).

Usage:
    python3 olk15_to_vcf.py INPUT_FOLDER [OUTPUT_FOLDER] [--combined] [--debug]

Each .olk15Contact file starts with a "CRTC" header, then a table of
(tag, size) records, then the values packed back to back. Tag = type in the
top byte (0x1f = UTF-16LE string, 0x1d = UTF-8 string) and field ID in the low
bits. Field IDs below were worked out from sample files.
"""
import re
import struct
import sys
from html import unescape
from pathlib import Path

FIELD_FIRST, FIELD_LAST, FIELD_NOTES = 0x01, 0x02, 0x04
FIELD_COMPANY, FIELD_TITLE = 0x14, 0x15
FIELD_STREET, FIELD_CITY, FIELD_STATE, FIELD_ZIP, FIELD_COUNTRY = 0x16, 0x17, 0x18, 0x19, 0x1A
FIELD_PHONES = (0x1D, 0x1E, 0x21)          # exact phone types (work/fax/mobile) unconfirmed
FIELD_URL = 0x20
FIELD_EMAILS = (0x66, 0x67, 0x68)


def parse(path: Path) -> dict:
    """Return {field_id: str} for string fields in the file."""
    d = path.read_bytes()
    i = d.find(b"CRTC")
    if i < 0:
        raise ValueError("no CRTC header")
    count = struct.unpack_from("<I", d, i + 8)[0]
    pos = i + 20
    if count > 1000 or pos + count * 8 > len(d):
        raise ValueError("unexpected record table")
    recs = []
    for _ in range(count):
        tag, size = struct.unpack_from("<II", d, pos)
        pos += 8
        recs.append((tag, size))
    fields = {}
    for tag, size in recs:
        raw = d[pos:pos + size]
        pos += size
        typ, fid = tag >> 24, tag & 0xFFFFFF
        if typ == 0x1F:
            val = raw.decode("utf-16-le", "replace")
        elif typ == 0x1D:
            val = raw.decode("utf-8", "replace")
        else:
            continue
        val = val.replace("\x00", "").strip()
        if val and fid not in fields:
            fields[fid] = val
    return fields


def html_to_text(s: str) -> str:
    s = re.sub(r"(?i)</div>|<br\s*/?>|</p>", "\n", s)
    s = unescape(re.sub(r"<[^>]+>", "", s))
    return re.sub(r"\n{2,}", "\n", s).strip()


def esc(v: str) -> str:
    return (v.replace("\\", "\\\\").replace(",", "\\,").replace(";", "\\;")
             .replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n"))


def fold(line: str) -> str:
    b, out = line.encode("utf-8"), []
    while len(b) > 75:
        cut = 75
        while (b[cut] & 0xC0) == 0x80:      # don't split a multibyte char
            cut -= 1
        out.append(b[:cut].decode("utf-8"))
        b = b[cut:]
        b = b" " + b
    out.append(b.decode("utf-8"))
    return "\r\n".join(out)


def make_vcard(f: dict) -> str:
    first, last = f.get(FIELD_FIRST, ""), f.get(FIELD_LAST, "")
    org = f.get(FIELD_COMPANY, "")
    emails = [f[k] for k in FIELD_EMAILS if k in f]
    full = f"{first} {last}".strip() or org or (emails[0] if emails else "Unknown")
    L = ["BEGIN:VCARD", "VERSION:3.0", f"N:{esc(last)};{esc(first)};;;", f"FN:{esc(full)}"]
    if org:
        L.append(f"ORG:{esc(org)}")
    if FIELD_TITLE in f:
        L.append(f"TITLE:{esc(f[FIELD_TITLE])}")
    for n, e in enumerate(emails):
        L.append(f"EMAIL;TYPE=INTERNET{';TYPE=PREF' if n == 0 else ''}:{e}")
    for k in FIELD_PHONES:
        if k in f:
            L.append(f"TEL{';TYPE=WORK' if k == FIELD_PHONES[0] else ''}:{esc(f[k])}")
    adr = [f.get(k, "") for k in (FIELD_STREET, FIELD_CITY, FIELD_STATE, FIELD_ZIP, FIELD_COUNTRY)]
    if any(adr):
        L.append("ADR;TYPE=WORK:;;" + ";".join(esc(a) for a in adr))
    if FIELD_URL in f:
        L.append(f"URL:{f[FIELD_URL]}")
    notes = html_to_text(f.get(FIELD_NOTES, ""))
    if notes:
        L.append(f"NOTE:{esc(notes)}")
    L.append("END:VCARD")
    return "\r\n".join(fold(x) for x in L) + "\r\n"


def safe(s: str) -> str:
    return re.sub(r"[^\w.-]+", "_", s).strip("_")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    debug, combined = "--debug" in sys.argv, "--combined" in sys.argv
    src = Path(args[0]).expanduser()
    dst = Path(args[1]).expanduser() if len(args) > 1 else src / "vcf_output"
    dst.mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in src.rglob("*") if p.suffix.lower() == ".olk15contact")
    print(f"Found {len(files)} .olk15Contact file(s)")

    cards, review = [], []
    for p in files:
        try:
            f = parse(p)
        except Exception as e:
            review.append((p.name, f"could not parse: {e}"))
            continue
        if debug:
            print(p.name, {hex(k): v[:40] for k, v in f.items()})
        if FIELD_FIRST not in f and FIELD_LAST not in f:
            review.append((p.name, "no name"))
        if not any(k in f for k in FIELD_EMAILS):
            review.append((p.name, "no email address"))
        card = make_vcard(f)
        cards.append(card)
        base = safe(f"{f.get(FIELD_FIRST, '')}_{f.get(FIELD_LAST, '')}") or safe(f.get(FIELD_COMPANY, "")) or p.stem
        out, n = dst / f"{base}.vcf", 2
        while out.exists():
            out, n = dst / f"{base}_{n}.vcf", n + 1
        with open(out, "w", encoding="utf-8", newline="") as fh:
            fh.write(card)

    if combined and cards:
        with open(dst / "all_contacts.vcf", "w", encoding="utf-8", newline="") as fh:
            fh.write("".join(cards))
    print(f"Wrote {len(cards)} vCard(s) to {dst}")
    for name, why in review:
        print(f"  check: {name}: {why}")


if __name__ == "__main__":
    main()
