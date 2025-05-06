import unreal
import json
import os

# 環境変数 REPORT_ROOT を使用。未設定の場合は C:\UnrealReport
output_dir = os.environ.get("REPORT_ROOT", r"C:\UnrealReport")
output_file = os.path.join(output_dir, "map_list.json")
if not os.path.exists(output_dir):
    os.makedirs(output_dir)

# アセット取得
asset_registry = unreal.AssetRegistryHelpers.get_asset_registry()
class_path = unreal.TopLevelAssetPath("/Script/Engine", "World")
map_assets = asset_registry.get_assets_by_class(class_path, True)

wp_maps = []
level_maps = []

for asset in map_assets:
    map_path = str(asset.package_name)
    world = unreal.EditorAssetLibrary.load_asset(map_path)
    if isinstance(world, unreal.World):
        world_settings = world.get_world_settings()
        world_partition = world_settings.get_editor_property("world_partition")
        if world_partition:
            wp_maps.append(map_path)
        else:
            level_maps.append(map_path)

# JSON 書き出し
output_data = {
    "wp": wp_maps,
    "level": level_maps
}

with open(output_file, "w", encoding="utf-8") as f:
    json.dump(output_data, f, indent=2)

unreal.log(f"Map list written to: {output_file}")
