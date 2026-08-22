# -*- coding: utf-8 -*-
"""
factbase_from_case.py — 把 prospectus-extractor 的單一資料源 case_data.json
(= 35分頁 Excel 的同源) 渲染成 vc-investment-evaluator Step D 吃的 Factbase.md (A-G)。

設計原則:
  - 單一資料源 case_data.json → 同時 render 兩個產物:
      build_excel.py  → {case}_Prospectus_extract.xlsx  (人看/附錄/對帳)
      本檔            → {case}_Factbase.md               (evaluator/下游渲染器使用)
  - 不改 evaluator 吃 factbase.md 的邏輯;只是把萃取結果用它要的格式輸出。
  - 逐項不刪減:歷史 IS/BS/CF 與沿革/團隊/股本 等原樣搬進對應 A-G 區塊。
用法: python3 factbase_from_case.py case_data.json {case_id}_Factbase.md
"""
import sys, json
from pathlib import Path

from prospectus_contract import status_label
from validate_case_data import validate_data

# 母版分頁 -> factbase 七大類 (A-G) 對映
GROUP = {
 "A 公司基本資料": ["00_封面","25_轉投資","12_從業員工人數"],
 "B 股東結構": ["02_股本形成","05_主要股東"],
 "C 董監事 + 經營團隊": ["03_董監事","04_經營團隊"],
 "D 財務數據(逐項不刪減)": ["27_歷年財務摘要5年","28甲_損益表","28乙_資產負債表","28丙_現金流量表","查核意見_明細"],
 "E 產品/技術/產業": ["06_產品營收比重","07_目前產品與服務","08_未來新產品服務","09_未來研發計畫",
                "10_研發成功技術","11_研發人員學經歷","13_產品用途","14_產製過程","15_毛利率變化",
                "19_銷售量值","20_生產量值","21_產能利用率","22_產業概況","23_中下游關聯","24_競爭情勢"],
 "F 客戶與供應商": ["17_主要供應商","18_主要客戶","16_銷售地區","26_重要契約"],
 "G 本輪條件 & IPO規劃 & 財測": ["財務預測","紅旗"],  # 紅旗/本輪/財測;封面亦含本輪摘要
}

def md_table(header, rows):
    out = []
    if header:
        out.append("| " + " | ".join(str(h) for h in header) + " |")
        out.append("|" + "|".join(["---"]*len(header)) + "|")
    for r in rows:
        cells = [str(c).replace("\n"," ").replace("|","/") for c in r]
        out.append("| " + " | ".join(cells) + " |")
    return "\n".join(out)

def render_text(data):
    sheets = {s["name"]: s for s in data.get("sheets",[]) if s.get("name")}
    L = []
    case = data.get("case", {})
    L.append("# " + case.get("title", data.get("title", "Factbase")))
    L.append("*由 prospectus-extractor 之 case_data 渲染 (與 35分頁 Excel 同源)；逐項不刪減，每筆標來源。*\n")
    for grp, names in GROUP.items():
        L.append(f"\n## {grp}")
        emitted = False
        for nm in names:
            sh = sheets.get(nm)
            if sh and sh.get("rows"):
                emitted = True
                L.append(f"\n### {nm}")
                hdr = sh.get("header")
                if sh.get("no_header"):  # 封面式 kv
                    L.append(md_table(["項目","內容"], sh["rows"]))
                else:
                    L.append(md_table(hdr, sh["rows"]))
                for n in sh.get("notes",[]):
                    L.append(f"> {n}")
            elif sh:
                label = status_label(sh.get("status", "missing"))
                reason = sh.get("reason") or "未提供原因"
                L.append(f"\n### {nm}\n> {label}：{reason}")
        if not emitted and grp.startswith("G"):
            # G 區常缺:提示由 data room 他檔/evaluator 後段補
            L.append("> 本輪 Term Sheet/估值/IRR 多不在萃取範圍；見封面摘要與紅旗，IRR 由 evaluator Phase 5B 補。")
    # 附:缺頁總表 (與 Excel 缺頁一致)
    unavailable = [
        [s["name"], status_label(s["status"]), s.get("reason") or ""]
        for s in data.get("sheets", [])
        if s.get("status") in ("missing", "not_applicable")
    ]
    if unavailable:
        L.append("\n## 缺失／不適用分頁（與 Excel 母版一致）")
        L.append(md_table(["分頁", "狀態", "原因"], unavailable))
    return "\n".join(L) + "\n"


def render(data, out):
    txt = render_text(data)
    Path(out).write_bytes(txt.encode("utf-8"))
    return txt

if __name__ == "__main__":
    data = json.load(open(sys.argv[1],encoding="utf-8"))
    validation = validate_data(data)
    if validation["status"] != "success":
        print(json.dumps(validation, ensure_ascii=False, indent=2), file=sys.stderr)
        raise SystemExit(2)
    txt = render(data, sys.argv[2])
    print("WROTE", sys.argv[2], "chars=", len(txt))
