"""Open the generated workbook in an isolated, hidden Excel instance."""
from __future__ import annotations

import json
from pathlib import Path

import pymupdf
import pythoncom
import pywintypes
import win32com.client

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "JBossEAP81_ALB_HTTPS_Redirect_Report.xlsx"
PREVIEW = ROOT.parent / ".validation" / "previews"


def inspect():
    PREVIEW.mkdir(parents=True, exist_ok=True)
    pythoncom.CoInitialize()
    excel = None
    workbook = None
    records = []
    try:
        excel = win32com.client.DispatchEx("Excel.Application")
        excel.Visible = False
        excel.DisplayAlerts = False
        excel.AutomationSecurity = 3  # Force-disable macros; generated file has none.
        workbook = excel.Workbooks.Open(str(BOOK), UpdateLinks=0, ReadOnly=True, IgnoreReadOnlyRecommended=True, AddToMru=False)
        for worksheet in workbook.Worksheets:
            name = worksheet.Name
            font = worksheet.UsedRange.Font.Name
            if font != "Meiryo UI":
                raise AssertionError(f"Unexpected native Excel font for {name}: {font}")
            if not worksheet.PageSetup.PrintArea:
                raise AssertionError(f"Missing native print area: {name}")
            records.append({"sheet": name, "font": font, "used_rows": worksheet.UsedRange.Rows.Count, "print_area": worksheet.PageSetup.PrintArea})
        for name in ("00_表紙と目次", "03_原理と通信図", "07_Undertow設定", "08_稼働中のCLI", "18_出典"):
            pdf = PREVIEW / f"{name}.pdf"
            workbook.Worksheets(name).ExportAsFixedFormat(0, str(pdf), 0, True, False)
            doc = pymupdf.open(pdf)
            try:
                for page in range(min(2, doc.page_count)):
                    doc[page].get_pixmap(matrix=pymupdf.Matrix(1.7, 1.7)).save(PREVIEW / f"{name}_p{page + 1}.png")
                records.append({"preview": name, "pdf_pages": doc.page_count, "rendered_first_pages": min(2, doc.page_count)})
            finally:
                doc.close()
        version = excel.Version
        result = {"status": "PASS", "excel_version": version, "read_only_open": True, "visible": False, "records": records, "scope": "Native Excel opening/fonts/print-area/export only; not application runtime verification"}
        ROOT.joinpath("native_excel_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"PASS: Native Excel {version}, {workbook.Worksheets.Count} worksheets, read-only open and five chapter PDF previews.")
    except pywintypes.com_error as exc:
        result = {"status": "UNAVAILABLE", "hresult": f"0x{exc.hresult & 0xffffffff:08X}", "scope": "Excel COM opening/export could not be completed in this environment; use structural and Pillow checks separately"}
        ROOT.joinpath("native_excel_validation.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        raise
    finally:
        if workbook is not None:
            workbook.Close(False)
        if excel is not None:
            excel.Quit()
        pythoncom.CoUninitialize()


if __name__ == "__main__":
    inspect()
