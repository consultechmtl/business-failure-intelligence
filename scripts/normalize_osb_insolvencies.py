#!/usr/bin/env python3
"""Normalize official OSB BIA insolvency workbook observations (stdlib only)."""
import argparse, csv, datetime as dt, re, zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

MONTHS = {"jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6, "july": 7, "aug": 8, "sept": 9, "oct": 10, "nov": 11, "dec": 12}
PROVINCES = {"Quebec/Québec": "Quebec", "Canada/Canada": "Canada"}
SOURCE = "https://ised-isde.canada.ca/site/office-superintendent-bankruptcy/sites/default/files/documents/insolvency_statistiques_insolvabilite_march_2026.xlsx"
FIELDS = ["osb_insolvency_observation_id","dataset_id","reference_period","geo","geo_level","debtor_type","business_form","insolvency_type","naics","measure","uom","value","status","source_url","retrieval_date"]

def clean(value): return re.sub(r"\s+", " ", (value or "").replace("\n", " ")).strip()
def cell_col(ref): return re.match(r"[A-Z]+", ref).group(0)
def workbook_rows(path, sheet=1):
    ns={"m":"http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    with zipfile.ZipFile(path) as z:
        strings=["".join(t.text or "" for t in s.findall(".//m:t",ns)) for s in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si",ns)]
        root=ET.fromstring(z.read(f"xl/worksheets/sheet{sheet}.xml"))
        rows=[]
        for row in root.findall(".//m:sheetData/m:row",ns):
            values={}
            for c in row.findall("m:c",ns):
                v=c.find("m:v",ns); value="" if v is None else v.text
                if c.attrib.get("t")=="s" and value: value=strings[int(value)]
                values[cell_col(c.attrib["r"])]=clean(value)
            maximum=max([ord(k)-64 for k in values] or [1]); rows.append([values.get(chr(64+i),"") for i in range(1,maximum+1)])
        return rows

def month(value):
    token=clean(value).split("/")[0].lower()
    return MONTHS.get(token)
def section(label):
    label=clean(label)
    if "Filed by Businesses" in label: return ("business","all_businesses",None,"province")
    if "Filed by Corporations" in label: return ("business","corporation",None,"province")
    if "Individual Businesses" in label: return ("business","individual_business",None,"province")
    if "by NAICS" in label: return ("all","all",None,"naics")
    if "Filed by Consumers" in label: return ("consumer","not_applicable",None,"province")
    if label.startswith("Total BIA Insolvencies"): return ("all","all",None,"province")
    return None
def geo_name(label): return PROVINCES.get(clean(label), clean(label).split("/")[0])
def insolvency(label):
    if "Bankruptc" in label or "Faillite" in label: return "Bankruptcy"
    if "Proposal" in label or "Proposition" in label: return "Proposal"
    return "Total"
def normalize_sheet(rows, year, source_url, retrieval_date):
    output=[]; active=None; periods=[]; parent=None
    for row in rows:
        label=clean(row[0] if row else "")
        new=section(label)
        if new: active=new; parent=None; continue
        if not active: continue
        header=[month(x) for x in row[1:]]
        if any(header): periods=header; continue
        if not label or not periods: continue
        typ=insolvency(label)
        if typ != "Total" and parent is None: continue
        if typ == "Total": parent=label; continue
        debtor, form, _, geography=active
        geo="Canada" if geography=="naics" else geo_name(parent)
        naics=parent if geography=="naics" else "not_available"
        for index, value in enumerate(row[1:]):
            if index >= len(periods) or not periods[index] or not value: continue
            try: numeric=float(value.replace(",", ""))
            except ValueError: continue
            period=f"{year}-{periods[index]:02d}"
            key="|".join([period,geo,debtor,form,typ,naics,"Volume"])
            output.append({"osb_insolvency_observation_id":"osb-"+__import__("hashlib").sha256(key.encode()).hexdigest()[:20],"dataset_id":"osb-bia-insolvency-statistics-2026-03","reference_period":period,"geo":geo,"geo_level":"province" if geography=="province" else "country","debtor_type":debtor,"business_form":form,"insolvency_type":typ,"naics":naics,"measure":"Volume","uom":"Number","value":str(int(numeric) if numeric.is_integer() else numeric),"status":"published","source_url":source_url,"retrieval_date":retrieval_date})
    return output
def main():
    p=argparse.ArgumentParser(); p.add_argument("workbook",type=Path); p.add_argument("--output",type=Path,default=Path(__file__).resolve().parents[1]/"data/curated/osb_insolvency_observations.csv"); p.add_argument("--retrieval-date",default=dt.date.today().isoformat()); p.add_argument("--source-url",default=SOURCE); args=p.parse_args()
    rows=normalize_sheet(workbook_rows(args.workbook),2026,args.source_url,args.retrieval_date)
    args.output.parent.mkdir(parents=True,exist_ok=True)
    with args.output.open("w", newline="", encoding="utf-8") as f: w=csv.DictWriter(f, fieldnames=FIELDS, lineterminator="\n"); w.writeheader(); w.writerows(rows)
    print(f"Normalized {len(rows)} OSB observations to {args.output}")
if __name__ == '__main__': main()
