import unreal
import csv
import os
import hashlib

asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
editor_asset_lib = unreal.EditorAssetLibrary
editor_level_lib = unreal.EditorLevelLibrary

class_path = unreal.TopLevelAssetPath("/Script/Engine", "World")

dependency_options_soft = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=True,
    include_hard_package_references=False,
    include_searchable_names=False,
    include_soft_management_references=False,
    include_hard_management_references=False
)

dependency_options_hard = unreal.AssetRegistryDependencyOptions(
    include_soft_package_references=False,
    include_hard_package_references=True,
    include_searchable_names=False,
    include_soft_management_references=False,
    include_hard_management_references=False
)

map_assets = asset_registry.get_assets_by_class(class_path, True)

project_dir = unreal.Paths.project_dir()
project_name = os.path.basename(os.path.normpath(project_dir))

# Use REPORT_ROOT environment variable or fallback to default
report_root = os.environ.get("REPORT_ROOT", "C:/UnrealReport")

external_actor_class_cache = {}

def preload_external_actor_classes(map_path):
    try:
        editor_level_lib.load_level(map_path)
        for actor in editor_level_lib.get_all_level_actors():
            path = actor.get_path_name()
            class_name = actor.get_class().get_name()
            external_actor_class_cache[path] = class_name
    except Exception as e:
        unreal.log_warning(f"Failed to preload external actors for {map_path}: {e}")

def get_class_name(asset_path, map_path=None):
    if asset_path.startswith("/Script/"):
        return "ScriptClass"
    if "/__ExternalActors__/" in asset_path:
        if map_path:
            preload_external_actor_classes(map_path)
            for path, class_name in external_actor_class_cache.items():
                if asset_path.endswith(path.split(".")[-1]):
                    return class_name
        return "ExternalActor"
    try:
        asset = editor_asset_lib.load_asset(asset_path)
        if asset:
            return asset.get_class().get_name()
    except Exception:
        return "LoadError"
    return "Unknown"

def get_file_size_kb(asset_path):
    if asset_path.startswith("/Script/"):
        return 0.0
    try:
        package_filename = unreal.EditorAssetLibrary.find_package_path(asset_path)
        if not package_filename:
            return 0.0
        abs_path = unreal.Paths.convert_relative_path_to_full(package_filename + ".uasset")
        if os.path.exists(abs_path):
            return round(os.path.getsize(abs_path) / 1024, 1)
    except:
        pass
    return 0.0

for asset_data in map_assets:
    map_path = str(asset_data.package_name)

    if "/Developers/" in map_path:
        continue

    map_name = os.path.basename(map_path)
    map_base_name = os.path.splitext(map_name)[0]
    dir_path = os.path.dirname(map_path)
    dir_hash = hashlib.md5(dir_path.encode('utf-8')).hexdigest()[:8]

    # World Partition 有効フラグの取得
    is_wp_enabled = False
    try:
        world = editor_asset_lib.load_asset(map_path)
        if world:
            world_settings = world.get_world_settings()
            world_partition = world_settings.get_editor_property("world_partition")
            is_wp_enabled = bool(world_partition)
    except Exception as e:
        unreal.log_warning(f"Could not determine WP status for {map_path}: {e}")

    # フォルダ名とファイル名の構築
    wp_suffix = " (WP)" if is_wp_enabled else ""
    folder_name = f"{map_base_name}_{dir_hash}{wp_suffix}"
    output_dir = os.path.join(report_root, project_name, folder_name)
    os.makedirs(output_dir, exist_ok=True)

    filename = f"{map_base_name}_{dir_hash}.csv"
    output_path = os.path.join(output_dir, filename)

    dependency_info = []
    visited = set()

    def collect_dependencies(parent_path, current_depth=1):
        if current_depth > 100:
            return

        hard_deps = asset_registry.get_dependencies(parent_path, dependency_options_hard)
        soft_deps = asset_registry.get_dependencies(parent_path, dependency_options_soft)

        for dep_set, ref_type in [(hard_deps, "Hard"), (soft_deps, "Soft")]:
            for d in dep_set:
                dep_str = str(d)
                if dep_str in visited:
                    continue
                visited.add(dep_str)

                try:
                    exists = False if dep_str.startswith("/Script/") else editor_asset_lib.does_asset_exist(dep_str)
                except Exception as e:
                    unreal.log_warning(f"Asset existence check failed for {dep_str}: {e}")
                    exists = "failed"

                class_name = get_class_name(dep_str, map_path)
                file_size_kb = get_file_size_kb(dep_str)

                row = {
                    "AssetPath": dep_str,
                    "ParentAsset": parent_path,
                    "Exists": exists,
                    "ReferenceType": ref_type,
                    "Depth": current_depth,
                    "AssetClass": class_name,
                    "FileSizeKB": file_size_kb
                }

                if is_wp_enabled and current_depth == 1 and exists == True:
                    try:
                        asset = editor_asset_lib.load_asset(dep_str)
                        if asset and asset.get_class().is_child_of(unreal.Actor):
                            if asset.has_editor_property("is_spatially_loaded"):
                                row["IsSpatiallyLoaded"] = asset.get_editor_property("is_spatially_loaded")
                            else:
                                row["IsSpatiallyLoaded"] = "N/A"
                    except Exception as e:
                        row["IsSpatiallyLoaded"] = f"Error: {e}"

                dependency_info.append(row)
                collect_dependencies(dep_str, current_depth + 1)

    collect_dependencies(map_path)

    base_fields = [
        "AssetPath", "ParentAsset", "Exists", "ReferenceType",
        "Depth", "AssetClass", "FileSizeKB"
    ]
    if any("IsSpatiallyLoaded" in row for row in dependency_info):
        base_fields.append("IsSpatiallyLoaded")

    fieldnames = base_fields

    with open(output_path, mode='w', newline='', encoding='utf-8') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        writer.writeheader()
        for info in dependency_info:
            writer.writerow(info)

    html_path = os.path.splitext(output_path)[0] + ".html"
    html_lines = []
    html_lines.append("<!DOCTYPE html>")
    html_lines.append("<html>")
    html_lines.append("<head>")
    html_lines.append("    <meta charset='utf-8'>")
    title = f"Dependency Report - {map_name} ({map_path})"
    if is_wp_enabled:
        title = f"{title} (WP Enabled)"
    html_lines.append(f"    <title>{title}</title>")
    html_lines.append("    <script src='https://cdn.jsdelivr.net/npm/jquery@3.6.0/dist/jquery.min.js'></script>")
    html_lines.append("    <script src='https://cdn.jsdelivr.net/npm/tablesorter@2.31.3/dist/js/jquery.tablesorter.min.js'></script>")
    html_lines.append("    <script src='https://cdn.jsdelivr.net/npm/tablesorter@2.31.3/dist/js/widgets/widget-filter.min.js'></script>")
    html_lines.append("    <link href='https://cdn.jsdelivr.net/npm/tablesorter@2.31.3/dist/css/theme.default.min.css' rel='stylesheet'>")
    html_lines.append("</head>")
    html_lines.append("<body>")
    html_lines.append(f"    <h1>{title}</h1>")
    html_lines.append("    <table id='dependencyTable' class='tablesorter'>")
    html_lines.append("        <thead>")
    html_lines.append("            <tr>")
    for key in fieldnames:
        html_lines.append(f"                <th>{key}</th>")
    html_lines.append("            </tr>")
    html_lines.append("        </thead>")
    html_lines.append("        <tbody>")
    for row in dependency_info:
        html_lines.append("            <tr>")
        for key in fieldnames:
            val = row.get(key)
            html_lines.append(f"                <td>{'' if val is None else str(val)}</td>")
        html_lines.append("            </tr>")
    html_lines.append("        </tbody>")
    html_lines.append("    </table>")
    html_lines.append("    <script>")
    html_lines.append("        $(function() {")
    html_lines.append("            $('#dependencyTable').tablesorter({")
    html_lines.append("                theme: 'default',")
    html_lines.append("                widgets: ['filter'],")
    html_lines.append("                widgetOptions: {")
    html_lines.append("                    filter_columnFilters: true")
    html_lines.append("                }")
    html_lines.append("            });")
    html_lines.append("            $('<button>Reset Filters</button>').click(function() {")
    html_lines.append("                $('#dependencyTable').trigger('filterReset');")
    html_lines.append("            }).insertBefore('#dependencyTable');")
    html_lines.append("        });")
    html_lines.append("    </script>")
    html_lines.append("</body>")
    html_lines.append("</html>")

    with open(html_path, "w", encoding="utf-8") as htmlfile:
        htmlfile.write("\n".join(html_lines))

    unreal.log(f"Exported map dependency tree (depth 100) for {map_path} to {output_path}")
    unreal.log(f"Exported HTML report to {html_path}")
