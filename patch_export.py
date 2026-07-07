import pandas as pd
import io

def generate_consolidado_inline_excel(payload: dict) -> bytes:
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="xlsxwriter") as writer:
        pd.DataFrame().to_excel(writer, index=False, sheet_name="Consolidado")
        wb = writer.book
        ws = writer.sheets["Consolidado"]
        ws.freeze_panes(1, 0)
        
        # Formats
        header_fmt = wb.add_format({"bold": True, "font_color": "white", "bg_color": "#17365D", "border": 1, "align": "center", "valign": "vcenter"})
        header_fat_fmt = wb.add_format({"bold": True, "font_color": "#000000", "bg_color": "#FFD966", "border": 1, "align": "center", "valign": "vcenter"})
        
        unit_fmt = wb.add_format({"bold": True, "bg_color": "#002E7A", "font_color": "white", "border": 1})
        unit_money_fmt = wb.add_format({"bold": True, "bg_color": "#002E7A", "font_color": "white", "border": 1, "align": "right", "num_format": 'R$ #,##0.00'})
        
        detail_fmt = wb.add_format({"border": 1})
        detail_money_fmt = wb.add_format({"border": 1, "align": "right", "num_format": 'R$ #,##0.00'})
        detail_fat_money_fmt = wb.add_format({"border": 1, "align": "right", "bg_color": "#F2F2F2", "num_format": 'R$ #,##0.00'})
        obs_fmt = wb.add_format({"border": 1, "bg_color": "#FFF2CC"})
        
        # Write headers
        columns = payload["columns"]
        for col_idx, col in enumerate(columns):
            label = str(col["label"]).upper()
            fmt = header_fat_fmt if col["kind"] == "fat" else header_fmt
            ws.write(0, col_idx, label, fmt)
            
            # Set column widths
            if col["key"] == "label":
                ws.set_column(col_idx, col_idx, 35)
            elif col["kind"] == "observation":
                ws.set_column(col_idx, col_idx, 50)
            else:
                ws.set_column(col_idx, col_idx, 18)
        
        # Write rows
        current_row = 1
        for row in payload["rows"]:
            if row["type"] == "unit":
                ws.write(current_row, 0, str(row["label"]).upper(), unit_fmt)
                for col_idx, col in enumerate(columns[1:], 1):
                    if col["kind"] in ("money", "fat"):
                        val = row["values"].get(col["key"], "")
                        try:
                            if val: val = float(val)
                        except: pass
                        ws.write(current_row, col_idx, val if val != "" else 0, unit_money_fmt)
                    elif col["kind"] == "observation":
                        ws.write(current_row, col_idx, "", unit_fmt)
            else:
                operadora = row["label"]
                if row.get("signal"):
                    operadora = f"[{row['signal'].upper()}] {operadora}"
                ws.write(current_row, 0, operadora, detail_fmt)
                
                for col_idx, col in enumerate(columns[1:], 1):
                    if col["kind"] in ("money", "fat"):
                        val = row["values"].get(col["key"], "")
                        try:
                            if val: val = float(val)
                        except: pass
                        fmt = detail_fat_money_fmt if col["kind"] == "fat" else detail_money_fmt
                        ws.write(current_row, col_idx, val if val != "" else 0, fmt)
                    elif col["kind"] == "observation":
                        obs = str(row.get("observation", ""))
                        if row.get("manualComment"):
                            obs = f"{obs} | Manual: {row['manualComment']}" if obs else f"Manual: {row['manualComment']}"
                        ws.write(current_row, col_idx, obs, obs_fmt)
            current_row += 1
            
    return output.getvalue()
