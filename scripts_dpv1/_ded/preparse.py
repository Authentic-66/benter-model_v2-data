"""Read-only pre-parse of every staged DED chart (Stage 1). Writes JSON to _ded/parsed/ only."""
import sys, json, glob, time, re
from pathlib import Path
sys.path.insert(0, '.'); sys.path.insert(0, '../scripts')
import logging; logging.disable(logging.WARNING)
import equibase_pdf_parser as parser
out = Path('_ded/parsed'); out.mkdir(parents=True, exist_ok=True)
rows = []
t0 = time.time()
for pdf in sorted(Path('../Delta Downs').glob('ded-results-*/*.pdf')):
    tgt = out / (pdf.stem + '.json')
    if tgt.exists():
        p = json.loads(tgt.read_text(encoding='utf-8'))
    else:
        try:
            p = parser.parse_pdf(pdf)
        except Exception as e:
            rows.append({'pdf': pdf.name, 'error': repr(e)}); continue
        tgt.write_text(json.dumps(p), encoding='utf-8')
print(f"parsed in {time.time()-t0:.0f}s")
