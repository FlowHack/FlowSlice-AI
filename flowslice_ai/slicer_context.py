"""Разделы пресетов слайсера для сбора контекста."""

# Metadata-ключи пресетов: служебные поля JSON-профиля, НЕ настройки.
# Исключаются из вывода контекста. Полезные параметры (printer_model,
# printer_variant, nozzle_diameter) в список НЕ входят и остаются в выводе.
PRESET_METADATA_KEYS: frozenset[str] = frozenset(
    {
        "name",
        "inherits",
        "from",
        "type",
        "version",
        "setting_id",
        "instantiation",
        "printer_settings_id",
        "print_settings_id",
        "filament_settings_id",
        "compatible_printers",
        "renamed_from",
        "default_print_profile",
        "default_filament_profile",
        "filament_id",
        "host_type",
        "printer_extruder_id",
        "printer_extruder_variant",
        "print_extruder_id",
        "print_extruder_variant",
        "filament_extruder_variant",
        "sync_info",
        "base_id",
        "user_id",
        "updated_time",
    }
)

# Разделы пресетов: ключ результата → (атрибут коллекции, поля для full_config_value).
PRESET_SECTIONS: dict[str, tuple[str, tuple[str, ...]]] = {
    "printer": (
        "printers",
        (
            "printer_model",
            "nozzle_diameter",
            "printable_height",
            "printable_width",
            "printable_depth",
            "printer_technology",
            "bed_shape",
            "bed_length",
            "bed_width",
            "max_print_height",
            "heated_bed",
            "heated_chamber",
            "chamber_temperature",
            "notes",
            "printer_notes",
            "machine_start_gcode",
            "machine_end_gcode",
        ),
    ),
    "filament": (
        "filaments",
        (
            "filament_type",
            "filament_vendor",
            "filament_density",
            "filament_cost",
            "filament_flow_ratio",
            "filament_flow_ratio_initial_layer",
            "nozzle_temperature",
            "nozzle_temperature_initial_layer",
            "bed_temperature",
            "chamber_temperature",
            "notes",
            "filament_notes",
        ),
    ),
    "print": (
        "prints",
        (
            "layer_height",
            "initial_layer_print_height",
            "line_width",
            "wall_loops",
            "sparse_infill_density",
            "sparse_infill_pattern",
            "enable_support",
            "support_type",
            "default_print_speed",
            "outer_wall_speed",
            "travel_speed",
            "brim_type",
            "brim_width",
            "ironing_type",
            "notes",
            "print_notes",
        ),
    ),
}


def _overlapping_preset_fields() -> frozenset[str]:
    """Ключи, встречающиеся сразу в нескольких разделах пресетов.

    Объединённый `full_config_value()` не различает раздел, поэтому для таких
    ключей (например, `notes`, `chamber_temperature`) его значение может
    принадлежать чужому профилю. Их уточнение через merged-конфиг запрещено.
    """
    seen: set[str] = set()
    overlap: set[str] = set()
    for _attr, fields in PRESET_SECTIONS.values():
        for field in fields:
            if field in seen:
                overlap.add(field)
            seen.add(field)
    return frozenset(overlap)


AMBIGUOUS_PRESET_KEYS: frozenset[str] = _overlapping_preset_fields()
