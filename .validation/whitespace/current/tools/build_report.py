"""Build the local Excel report and diagrams from the authoritative Markdown."""
from __future__ import annotations

import json
import math
import re
from pathlib import Path

import xlsxwriter
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
MD = ROOT / "JBossEAP81_ALB_HTTPS_Redirect_Report.md"
BOOK = ROOT / "JBossEAP81_ALB_HTTPS_Redirect_Report.xlsx"
FONT_DIR = Path("C:/Windows/Fonts")
FONT_NAME = "Meiryo UI"
COL_WIDTHS = [18, 29, 33, 34, 28, 12]
COL_PIXELS = [int(x * 7 + 5) for x in COL_WIDTHS]
SHEET_NAMES = [
    "00_表紙と目次", "01_結論", "02_事実と未確認", "03_原理と通信図",
    "04_歴史と背景", "05_原因調査", "06_ALBの確認", "07_Undertow設定",
    "08_稼働中のCLI", "09_起動前の実装", "10_恒久化", "11_独自フィルタ",
    "12_redirect_socket", "13_検証手順", "14_適用と切り戻し", "15_疑問と誤解",
    "16_用語集", "17_実装ファイル", "18_出典", "19_確認範囲",
]


def ui_font(points: float, bold: bool = False, *, pixels: bool = False):
    font_size = int(round(points if pixels else points * 96 / 72))
    return ImageFont.truetype(str(FONT_DIR / ("meiryob.ttc" if bold else "meiryo.ttc")), font_size, index=2)


def wrap(text: str, font, width: int) -> list[str]:
    """Conservative character wrapping; preserve explicit line breaks."""
    output: list[str] = []
    for paragraph in str(text).split("\n"):
        if not paragraph:
            output.append("")
            continue
        line = ""
        for ch in paragraph:
            if line and font.getlength(line + ch) > width:
                output.append(line)
                line = ch
            else:
                line += ch
        output.append(line)
    return output


def text_height(text: str, pixel_width: int, points: float = 11, bold: bool = False) -> float:
    font = ui_font(points, bold)
    # Additional horizontal/vertical allowance accounts for Excel's line layout.
    count = len(wrap(text, font, max(pixel_width - 24, 20)))
    return max(23, count * (points * 1.55) + 11)


def draw_text(draw, text, xy, font, width, fill="#222222", spacing=10):
    y = xy[1]
    for line in wrap(text, font, width):
        draw.text((xy[0], y), line, font=font, fill=fill)
        y += font.size + spacing
    return y


def make_flow_diagram():
    assets = ROOT / "assets"
    assets.mkdir(exist_ok=True)
    img = Image.new("RGB", (1600, 720), "white")
    d = ImageDraw.Draw(img)
    title = ui_font(36, True, pixels=True)
    head = ui_font(29, True, pixels=True)
    body = ui_font(23, pixels=True)
    small = ui_font(19, pixels=True)
    d.rectangle((0, 0, 1599, 80), fill="#252525")
    d.text((44, 19), "HTTPS の情報は、ALB の先へメモで伝える", font=title, fill="white")
    d.text((44, 102), "説明用の構成：利用者 → HTTPS:443 → ALB → HTTP:8080 → JBoss EAP 8.1", font=body, fill="#333333")

    boxes = [
        ((42, 164, 425, 366), "ブラウザー", "公開 URL\nhttps://example.net/upload\n大きなファイルを POST"),
        ((592, 164, 990, 366), "ALB（HTTPS 終端）", "TLS はここで終端\n内側へ別の HTTP 接続\nX-Forwarded-Proto: https"),
        ((1152, 164, 1558, 366), "EAP / Undertow", "HTTP のリスナーで受信\nメモを読むかどうかで\nscheme の認識が変わる"),
    ]
    for (x1, y1, x2, y2), label, text in boxes:
        d.rounded_rectangle((x1, y1, x2, y2), radius=12, fill="#F1F1F1", outline="#555555", width=2)
        d.rectangle((x1 + 1, y1 + 1, x2 - 1, y1 + 53), fill="#474747")
        d.text((x1 + 20, y1 + 12), label, font=head, fill="white")
        draw_text(d, text, (x1 + 20, y1 + 70), body, x2 - x1 - 40, spacing=11)
    for x1, x2, label in [(435, 580, "HTTPS"), (1000, 1140, "HTTP")]:
        d.line((x1, 269, x2 - 15, 269), fill="#222222", width=5)
        d.polygon([(x2 - 20, 255), (x2, 269), (x2 - 20, 283)], fill="#222222")
        d.text((x1 + 14, 231), label, font=small, fill="#333333")

    d.text((46, 397), "ファイルサイズ超過 → 独自フィルタ → 相対 sendRedirect の例", font=head, fill="#222222")
    for y, label, text, note, dark in [
        (450, "変更前", "Location: http://example.net/multipartException", "メモを使わず scheme=http のまま", False),
        (570, "変更後", "Location: https://example.net/multipartException", "proxy-address-forwarding=true で scheme=https", True),
    ]:
        d.rounded_rectangle((42, y, 1558, y + 94), radius=8, fill="#353535" if dark else "#EAEAEA")
        fg = "white" if dark else "#222222"
        d.text((64, y + 15), label, font=head, fill=fg)
        d.text((244, y + 15), text, font=body, fill=fg)
        d.text((244, y + 57), note, font=small, fill=fg)
    d.text((45, 690), "前提：正しいメモが届き、信頼する経路だけで受信。http の絶対 URL を渡す実装は別途修正。", font=small, fill="#333333")
    out = assets / "https_flow.png"
    img.save(out, optimize=True)
    return out


REF_DEF = re.compile(r'^\[(S\d+)\]:\s+(https?://\S+)(?:\s+"(.*?)")?$', re.M)
REF_LINK = re.compile(r"\[([^\]]+)\]\[(S\d+)\]")


def plain(text: str) -> str:
    text = REF_LINK.sub(lambda m: f"{m.group(1)} [{m.group(2)}]", text)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)
    text = text.replace("**", "").replace("`", "")
    return text


def blocks(lines: list[str]):
    i = 0
    while i < len(lines):
        line = lines[i]
        if not line.strip() or REF_DEF.match(line):
            i += 1
            continue
        if line.startswith("### "):
            yield {"type": "heading", "text": line[4:]}
            i += 1
        elif line.startswith("```"):
            lang = line[3:].strip()
            i += 1
            code = []
            while i < len(lines) and not lines[i].startswith("```"):
                code.append(lines[i])
                i += 1
            if i == len(lines):
                raise ValueError("Unclosed Markdown fence")
            yield {"type": "code", "lang": lang, "lines": code}
            i += 1
        elif line.startswith("| "):
            rows = []
            while i < len(lines) and lines[i].startswith("| "):
                values = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r"\s*:?-+:?\s*", v) for v in values):
                    rows.append(values)
                i += 1
            if any(len(row) != len(rows[0]) for row in rows):
                raise ValueError(f"Irregular Markdown table: {rows}")
            yield {"type": "table", "headers": rows[0], "rows": rows[1:]}
        elif line.startswith("!["):
            m = re.match(r"!\[(.*?)\]\((.*?)\)", line)
            if not m:
                raise ValueError(line)
            yield {"type": "image", "caption": m.group(1), "path": m.group(2)}
            i += 1
        elif re.match(r"^\d+\. ", line):
            yield {"type": "item", "text": line}
            i += 1
        else:
            para = [line]
            i += 1
            while i < len(lines) and lines[i].strip() and not re.match(r"^(### |```|\| |!\[|\d+\. |\[S\d+\]:)", lines[i]):
                para.append(lines[i])
                i += 1
            yield {"type": "paragraph", "text": "\n".join(para)}


def spans_for_columns(count: int):
    if count == 3:
        return [(0, 0), (1, 2), (3, 4)]
    if count == 4:
        return [(0, 0), (1, 1), (2, 2), (3, 4)]
    if count == 5:
        return [(x, x) for x in range(5)]
    raise ValueError(f"Unsupported table width {count}")


def build():
    flow = make_flow_diagram()
    text = MD.read_text(encoding="utf-8")
    refs = {m.group(1): {"url": m.group(2), "title": m.group(3)} for m in REF_DEF.finditer(text)}
    body = REF_DEF.sub("", text)
    chunks = re.split(r"^## (.+)$", body, flags=re.M)
    chapters = [("表紙と目次", chunks[0].splitlines())]
    chapters += [(chunks[i], chunks[i + 1].splitlines()) for i in range(1, len(chunks), 2)]
    if len(chapters) != len(SHEET_NAMES):
        raise ValueError("Chapter/sheet mismatch")
    parsed = [[b for b in blocks(lines) if not (b.get("text", "").startswith("# "))] for _, lines in chapters]
    ROOT.joinpath("sources.json").write_text(json.dumps(refs, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    wb = xlsxwriter.Workbook(str(BOOK), {"strings_to_formulas": False, "strings_to_urls": False})
    wb.set_properties({"title": "JBoss EAP 8.1 / ALB HTTPS リダイレクト対応提案", "subject": "アップロードサイズ超過時の Location 修正", "author": "Codex", "comments": "公式資料調査: 2026-10-03; 実環境変更・実動作試験は未実施"})
    wb.formats[0].set_font_name(FONT_NAME)
    wb.formats[0].set_font_size(11)
    common = {"font_name": FONT_NAME, "font_size": 11, "font_color": "#222222", "valign": "top", "text_wrap": True}
    def fmt(**kwargs):
        return wb.add_format(common | kwargs)
    f_title = fmt(font_size=20, bold=True, bg_color="#252525", font_color="#FFFFFF", valign="vcenter")
    f_meta = fmt(font_size=10, bg_color="#E8E8E8", font_color="#444444", valign="vcenter")
    f_nav = fmt(font_size=10, underline=1, font_color="#222222", bg_color="#F5F5F5")
    f_note = fmt(font_size=10, font_color="#555555", bg_color="#F5F5F5")
    f_heading = fmt(font_size=12, bold=True, bg_color="#555555", font_color="#FFFFFF", valign="vcenter")
    f_para = fmt()
    f_emphasis = fmt(bold=True, bg_color="#F0F0F0", border=1, border_color="#B0B0B0")
    f_item = fmt(bg_color="#F5F5F5")
    f_code_label = fmt(font_size=9, font_color="#555555", bg_color="#EFEFEF", border=1, border_color="#D0D0D0")
    f_code = fmt(font_size=10, bg_color="#F6F6F6", border=1, border_color="#DADADA", indent=1)
    f_table_head = fmt(bold=True, bg_color="#474747", font_color="#FFFFFF", border=1, border_color="#A0A0A0")
    f_table = [fmt(bg_color=c, border=1, border_color="#C9C9C9") for c in ("#FFFFFF", "#F2F2F2")]
    f_source = fmt(font_size=9, font_color="#444444", underline=1, border=1, border_color="#DDDDDD")
    f_table_link = [fmt(bg_color=c, border=1, border_color="#C9C9C9", underline=1) for c in ("#FFFFFF", "#F2F2F2")]
    metadata = []

    for index, ((title, _), chapter_blocks) in enumerate(zip(chapters, parsed)):
        ws = wb.add_worksheet(SHEET_NAMES[index])
        ws.hide_gridlines(2)
        ws.set_zoom(85)
        ws.set_default_row(23)
        for col, width in enumerate(COL_WIDTHS):
            ws.set_column(col, col, width, f_para)
        ws.freeze_panes(4, 0)
        ws.set_tab_color("#333333" if index in (0, 1, 7, 8, 13) else "#999999")
        ws.set_landscape()
        ws.set_paper(9)  # A4
        ws.fit_to_pages(1, 0)
        ws.set_margins(0.28, 0.28, 0.35, 0.4)
        ws.repeat_rows(0, 3)
        ws.set_header('&L&"Meiryo UI,Regular"&9JBoss EAP 8.1 / ALB&R&"Meiryo UI,Regular"&9調査日 2026-10-03', {"margin": 0.14})
        ws.set_footer('&L&"Meiryo UI,Regular"&9実環境試験は別途実施&C&"Meiryo UI,Regular"&9' + SHEET_NAMES[index] + '&R&"Meiryo UI,Regular"&9&P / &N', {"margin": 0.18})
        shown_title = "JBoss EAP 8.1 / ALB  HTTPS リダイレクト対応提案" if index == 0 else title
        ws.merge_range(0, 0, 0, 5, shown_title, f_title)
        ws.set_row(0, text_height(shown_title, sum(COL_PIXELS), 20, True))
        ws.merge_range(1, 0, 1, 5, "対象：EAP 8.1 / AWS ALB  ｜  調査日：2026年10月3日  ｜  Meiryo UI / モノトーン", f_meta)
        ws.set_row(1, 25)
        ws.merge_range(2, 0, 2, 1, "表紙・目次へ", f_nav)
        ws.write_url(2, 0, "internal:'00_表紙と目次'!A1", f_nav, "表紙・目次へ")
        ws.merge_range(2, 2, 2, 5, "実測・仮説・期待値を区別  ｜  例示の名前・URLは実環境に合わせる", f_note)
        ws.set_row(2, 23)
        ws.set_row(3, 9)
        row = 4
        source_count = 0
        text_blocks = 0
        table_rows = 0

        def source_cell(at_row: int, source_ids: list[str], extra_note: str = ""):
            nonlocal source_count
            if source_ids:
                deduped = list(dict.fromkeys(source_ids))
                label = "\n".join(deduped)
                ws.write_url(at_row, 5, refs[deduped[0]]["url"], f_source, label)
                source_count += len(deduped)
                return text_height(label, COL_PIXELS[5], 9)
            if extra_note:
                ws.write_string(at_row, 5, extra_note, f_note)
            else:
                ws.write_blank(at_row, 5, None, f_para)
            return 23

        if index == 0:
            ws.merge_range(row, 0, row, 5, "本資料の使い方：01で対応を選び、08・09で実装し、13で確認する。18から公式資料へ移動できる。", f_heading)
            ws.set_row(row, 32)
            row += 2

        for block in chapter_blocks:
            kind = block["type"]
            if kind == "heading":
                row += 1
                value = plain(block["text"])
                ws.merge_range(row, 0, row, 5, value, f_heading)
                ws.set_row(row, text_height(value, sum(COL_PIXELS), 12, True))
                row += 1
            elif kind in ("paragraph", "item"):
                value = plain(block["text"])
                is_bold = block["text"].startswith("**")
                style = f_item if kind == "item" else f_emphasis if is_bold else f_para
                ws.merge_range(row, 0, row, 4, value, style)
                ids = re.findall(r"\[(S\d+)\]", block["text"])
                source_height = source_cell(row, ids)
                ws.set_row(row, max(text_height(value, sum(COL_PIXELS[:5]), 11, is_bold), source_height))
                row += 1
                text_blocks += 1
            elif kind == "code":
                language = block["lang"] or "text"
                for n, code_line in enumerate(block["lines"], 1):
                    ws.write_string(row, 0, f"{language} / {n:02}", f_code_label)
                    # write_string/merge_range stores code as literal text, never formulas.
                    ws.merge_range(row, 1, row, 4, code_line or " ", f_code)
                    ws.write_blank(row, 5, None, f_para)
                    ws.set_row(row, text_height(code_line or " ", sum(COL_PIXELS[1:5]), 10))
                    row += 1
                row += 1
            elif kind == "table":
                spans = spans_for_columns(len(block["headers"]))
                for is_head, cells in [(True, block["headers"])] + [(False, cells) for cells in block["rows"]]:
                    heights = []
                    source_ids = []
                    for col_index, (cell_text, (start, end)) in enumerate(zip(cells, spans)):
                        value = plain(cell_text)
                        style = f_table_head if is_head else f_table[(row + col_index // 100) % 2]
                        if start != end:
                            ws.merge_range(row, start, row, end, value, style)
                        else:
                            ws.write_string(row, start, value, style)
                        heights.append(text_height(value, sum(COL_PIXELS[start:end + 1]), 11, is_head))
                        source_ids += re.findall(r"S\d{2}", value)
                    if is_head:
                        ws.write_string(row, 5, "出典 / 注記", f_table_head)
                        heights.append(text_height("出典 / 注記", COL_PIXELS[5], 11, True))
                    else:
                        heights.append(source_cell(row, [x for x in source_ids if x in refs]))
                        if index == 18 and re.fullmatch(r"S\d+", cells[0]):
                            sid = cells[0]
                            ws.write_url(row, 0, refs[sid]["url"], f_table_link[row % 2], sid)
                            ws.write_url(row, 5, refs[sid]["url"], f_source, "公式 URL")
                    ws.set_row(row, max(heights))
                    row += 1
                    table_rows += not is_head
                row += 1
            elif kind == "image":
                ws.merge_range(row, 0, row, 5, block["caption"], f_note)
                ws.set_row(row, 28)
                row += 1
                scale = (sum(COL_PIXELS) - 18) / 1600
                reserve_pixels = math.ceil(720 * scale) + 18
                reserve_rows = math.ceil(reserve_pixels / 30)
                for image_row in range(row, row + reserve_rows):
                    ws.set_row(image_row, 22.5)
                ws.insert_image(row, 0, str(flow), {"x_scale": scale, "y_scale": scale, "x_offset": 6, "y_offset": 6, "description": block["caption"], "object_position": 1})
                row += reserve_rows + 1
            else:
                raise ValueError(kind)

        if index == 0:
            row += 1
            ws.merge_range(row, 0, row, 5, "目次（章名をクリックすると該当シートへ移動）", f_heading)
            ws.set_row(row, 30)
            row += 1
            for chapter_index in range(1, len(chapters)):
                label = chapters[chapter_index][0]
                ws.merge_range(row, 0, row, 4, label, f_nav)
                ws.write_url(row, 0, f"internal:'{SHEET_NAMES[chapter_index]}'!A1", f_nav, label)
                ws.write_string(row, 5, f"{chapter_index:02}", f_note)
                ws.set_row(row, 25)
                row += 1
        ws.print_area(0, 0, max(row - 1, 4), 5)
        ws.set_selection(0, 0, 0, 0)
        metadata.append({"sheet": SHEET_NAMES[index], "chapter": title, "rows": row, "text_blocks": text_blocks, "table_data_rows": table_rows, "citation_links": source_count})

    wb.close()
    result = {"font": FONT_NAME, "palette": "monochrome", "sheets": metadata, "markdown_characters": len(text), "source_count": len(refs), "workbook": BOOK.name}
    ROOT.joinpath("build_manifest.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"workbook": str(BOOK), "sheets": len(metadata), "rows": sum(x["rows"] for x in metadata), "sources": len(refs), "markdown_characters": len(text)}, ensure_ascii=False))


if __name__ == "__main__":
    build()
