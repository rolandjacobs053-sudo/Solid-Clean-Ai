import json
import sys
import time

import httpx

API = "http://localhost:8001/api"
SOURCES = [
    ("https://britishcleaningcouncil.org/2026/02/17/research-shows-steady-growth-in-the-cleaning-hygiene-and-waste-industry-available-on-request/", "report"),
    ("https://cleaningmag.com/news/newly-published-research-launched-at-manchester-cleaning-show-2026", "report"),
    ("https://www.inc.com/magazine/201606/sheila-marikar/two-maids-and-a-mop.html", "case_study"),
    ("https://www.bookingkoala.com/blog/10-million-in-revenue-in-7-5-years-ryan-k/", "case_study"),
    ("https://www.bookingkoala.com/blog/queen-bee-cleaning-from-nothing-to-5-million-in-revenue-cristobal/", "case_study"),
    ("https://www.getjobber.com/academy/cleaning/earth-love-cleaning/", "case_study"),
    ("https://builttosell.com/radio/episode-376/", "podcast"),
    ("https://nolteanalytics.com/how-to-value-janitorial-services/", "report"),
    ("https://www.bizbuysell.com/learning-center/valuation-benchmarks/cleaning-janitorial/", "report"),
    ("https://en.wikipedia.org/wiki/ISS_A/S", "case_study"),
    ("https://www.issworld.com/about-us/celebrating-125-years-of-iss", "case_study"),
    ("https://franchise.neighborly.com/molly-maid/start-your-own-home-cleaning-business", "case_study"),
    ("https://www.mollymaid.com/about/molly-maid-brand-entity/", "case_study"),
    ("https://en.wikipedia.org/wiki/Mitie", "case_study"),
    ("https://www.issa.com/articles/business-cleaning-bids-guide/", "web"),
    ("https://www.housecallpro.com/resources/how-to-bid-commercial-cleaning-contracts/", "web"),
    ("https://www.spotlessapp.io/blog/commercial-cleaning-contracts-guide", "web"),
    ("https://blueprintjanitorial.com/guides/how-to-get-office-cleaning-contracts", "web"),
    ("https://learn.sweptworks.com/janitorial-contract-bids", "web"),
    ("https://www.youtube.com/watch?v=QBqEBuQvuL8", "youtube"),
    ("https://www.youtube.com/watch?v=VTSHNRIiwMU", "youtube"),
    ("https://www.youtube.com/watch?v=nvget2U7vVw", "youtube"),
] + [(u, t) for u, t in (a.split("|") for a in sys.argv[1:])]

c = httpx.Client(timeout=240)
login = c.post(f"{API}/auth/login", json={"email": "admin@solidcleanltd.com", "password": "SolidClean#2026"})
login.raise_for_status()
c.headers["Cookie"] = "; ".join(f"{k}={v}" for k, v in login.cookies.items())
for url, stype in SOURCES:
    t = time.time()
    r = c.post(f"{API}/admin/knowledge/ingest", json={"url": url, "source_type": stype})
    print(json.dumps({"url": url, "status": r.status_code, "secs": round(time.time() - t), "result": r.json()}), flush=True)
