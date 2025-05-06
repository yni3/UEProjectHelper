import unreal
import os
import csv
import time

# プロジェクト名・出力先の設定
project_dir = unreal.Paths.project_dir()
project_name = os.path.basename(os.path.normpath(project_dir))

# 環境変数 REPORT_ROOT を取得。存在しない場合は C:/UnrealReport を使用
report_root = os.getenv("REPORT_ROOT", "C:/UnrealReport")
output_dir = os.path.join(report_root, project_name)
os.makedirs(output_dir, exist_ok=True)

# 出力ファイルパス
csv_raw = os.path.join(output_dir, "CVarDump.csv")
csv_fixed = os.path.join(output_dir, "CVarDump2.csv")
html_path = os.path.join(output_dir, "CVarDump.html")

# CVar 出力実行
unreal.SystemLibrary.execute_console_command(None, f'DumpCVars -showhelp -csv="{csv_raw}"')

# CSV 修正処理
def fix_csv(infile, outfile):
    valid_setby = {
        "Constructor", "Scalability", "GameSetting", "ProjectSetting",
        "DeviceProfile", "ConsoleVariablesIni", "Commandline", "Code", "Console"
    }

    fixed_rows = [["NAME", "VALUE", "SETBY", "HELP"]]

    with open(infile, encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader)

        for row in reader:
            if len(row) == 4:
                fixed_rows.append(row)
            elif len(row) >= 5:
                name = row[0]
                rest = row[1:]

                # SETBY 候補は末尾から順に探す
                found_index = None
                for i in reversed(range(len(rest))):
                    token = rest[i].strip()
                    if token in valid_setby:
                        found_index = i
                        break

                if found_index is not None:
                    setby = rest[found_index].strip()
                    value_and_help = rest[:found_index]
                    if len(value_and_help) >= 2:
                        value = value_and_help[0].strip().replace(",", "，")
                        help_text = ",".join(value_and_help[1:]).strip().replace(",", "，")
                    elif len(value_and_help) == 1:
                        value = value_and_help[0].strip().replace(",", "，")
                        help_text = ""
                    else:
                        value = ""
                        help_text = ""
                    fixed_rows.append([name, value, setby, help_text])
                else:
                    # SETBY 見つからなかった
                    help_text = ",".join(rest).replace(",", "，")
                    fixed_rows.append([name, "", "failed", help_text])
            else:
                unreal.log_warning(f"Malformed row skipped: {row}")

    with open(outfile, "w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerows(fixed_rows)

# HTML 出力処理
def convert_csv_to_html(csv_file, html_file):
    with open(csv_file, encoding="utf-8") as f:
        reader = csv.reader(f)
        rows = list(reader)

    with open(html_file, "w", encoding="utf-8") as f:
        f.write("<!DOCTYPE html>\n<html>\n<head>\n")
        f.write("  <meta charset='utf-8'>\n")
        f.write(f"  <title>{project_name} Console Variable Dump</title>\n")
        f.write("  <script src='https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js'></script>\n")
        f.write("  <script src='https://cdn.jsdelivr.net/npm/tablesorter@2.31.3/dist/js/jquery.tablesorter.min.js'></script>\n")
        f.write("  <script src='https://cdn.jsdelivr.net/npm/tablesorter@2.31.3/dist/js/widgets/widget-filter.min.js'></script>\n")
        f.write("  <link href='https://cdn.jsdelivr.net/npm/tablesorter@2.31.3/dist/css/theme.default.min.css' rel='stylesheet'>\n")
        f.write("</head>\n<body>\n")
        f.write(f"  <h1>{project_name} Console Variable Dump</h1>\n")
        f.write("  <button onclick=\"$('#cvarTable').trigger('filterReset');\">Reset Filters</button>\n")
        f.write("  <table id='cvarTable' class='tablesorter'>\n")
        f.write("    <thead><tr>" + "".join(f"<th>{col}</th>" for col in rows[0]) + "</tr></thead>\n")
        f.write("    <tbody>\n")
        for row in rows[1:]:
            f.write("      <tr>" + "".join(f"<td>{col}</td>" for col in row) + "</tr>\n")
        f.write("    </tbody>\n  </table>\n")
        f.write("  <script>\n")
        f.write("    $(function() {\n")
        f.write("      $('#cvarTable').tablesorter({ theme: 'default', widgets: ['filter'] });\n")
        f.write("    });\n")
        f.write("  </script>\n</body>\n</html>")

# 遅延後に CSV → HTML 変換
unreal.log("Waiting 5 seconds before parsing CSV...")
time.sleep(5)

if os.path.exists(csv_raw):
    fix_csv(csv_raw, csv_fixed)
    convert_csv_to_html(csv_fixed, html_path)
    unreal.log(f"Output CSV (fixed): {csv_fixed}")
    unreal.log(f"Output HTML: {html_path}")
else:
    unreal.log_warning(f"CSV not found: {csv_raw}")

# Editor 終了
unreal.SystemLibrary.quit_editor()
