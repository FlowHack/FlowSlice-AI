# pyright: ignore[reportGeneralTypeIssues]
"""Контекст слайсера и оценка токенов движка FlowSlice AI.

Миксин SlicerContextMixin собирает данные о модели на столе (через
orca.host.model()), активных пресетах печати (orca.host.preset_bundle()),
строит системный промпт и оценивает размер контекста в токенах.
"""
# pyright: ignore[reportGeneralTypeIssues]
# pylint: disable=too-many-lines,too-many-statements,too-many-branches,broad-exception-caught
# pylint: disable=too-many-locals,too-many-nested-blocks,too-many-public-methods,too-few-public-methods

import json
import sys
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

try:
    import orca
except ImportError:
    orca = None  # type: ignore[assignment]

from flowslice_ai.constants import SYSTEM_PROMPT
from flowslice_ai.logging import _LOGGER
from flowslice_ai.orca_compat import _HAS_NUMPY, _np
from flowslice_ai.slicer_context import PRESET_SECTIONS


class SlicerContextMixin:
    """Сбор контекста слайсера, системный промпт и оценка токенов."""

    def _collect_context(self: "_ChatEngine", flags: dict[str, Any]) -> dict[str, Any]:
        """Собирает контекст слайсера по включённым флагам."""
        ctx: dict[str, Any] = {}
        if flags.get("model"):
            ctx["model"] = self._collect_model_data()
        if flags.get("filament") or flags.get("printer") or flags.get("print"):
            ctx["presets"] = self._collect_preset_data()
        return ctx

    def _collect_model_data(self: "_ChatEngine") -> dict[str, Any]:
        """Собирает данные о модели на столе слайсера."""
        data: dict[str, Any] = {"objects": [], "coords": "world"}
        if orca is None:
            return data
        try:
            model = orca.host.model()
            for obj in model.objects():
                for vol in obj.volumes():
                    mesh = self._safe_get(vol, "mesh")
                    if mesh is None:
                        continue
                    bbox = self._safe_get(mesh, "bounding_box")
                    if bbox is not None:
                        size = getattr(bbox, "size", bbox)
                        if isinstance(size, (tuple, list)) and len(size) >= 3:
                            local_bbox = tuple(round(float(v), 1) for v in size[:3])
                        else:
                            local_bbox = ()
                    else:
                        local_bbox = ()
                    volume = self._safe_get(mesh, "volume")
                    entry: dict[str, Any] = {
                        "name": self._safe_get(vol, "name") or "",
                        "local_bbox_mm": local_bbox,
                        "volume_cm3": round(volume / 1000.0, 2) if volume else 0.0,
                        "manifold": bool(self._safe_get(mesh, "is_manifold")),
                        "triangles": self._safe_get(mesh, "triangle_count") or 0,
                    }
                    if _HAS_NUMPY:
                        entry.update(self._world_stats(obj, vol, mesh))
                    else:
                        entry["coords"] = "local"
                        entry.update(self._local_stats(obj))
                    data["objects"].append(entry)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать данные модели: %s", exc)
            data["objects"] = []
        return data

    def _world_stats(self: "_ChatEngine", obj: Any, vol: Any, mesh: Any) -> dict[str, Any]:
        """Считает мировые характеристики экземпляров через numpy."""
        assert _np is not None
        stats: dict[str, Any] = {"instances": []}
        try:
            verts = self._safe_get(mesh, "vertices")
            tris = self._safe_get(mesh, "triangles")
            vol_matrix = self._safe_get(vol, "matrix")
            if verts is None or tris is None or vol_matrix is None:
                return stats
            verts = _np.asarray(verts, dtype=_np.float64)
            tris = _np.asarray(tris)
            instances = self._safe_get(obj, "instances")
            if isinstance(instances, (list, tuple)):
                inst_list = instances
            else:
                inst_fn = getattr(obj, "instance", None)
                if not callable(inst_fn):
                    return stats
                inst_list = [inst_fn(i) for i in range(int(instances))]
            for index, inst in enumerate(inst_list):
                inst_matrix = self._safe_get(inst, "matrix")
                if inst_matrix is None:
                    continue
                world = (
                    _np.column_stack((verts, _np.ones(len(verts))))
                    @ (inst_matrix @ vol_matrix).T
                )[:, :3]
                bbox_min = world.min(axis=0)
                bbox_max = world.max(axis=0)
                tri_pts = world[tris]
                cross = _np.cross(
                    tri_pts[:, 1] - tri_pts[:, 0], tri_pts[:, 2] - tri_pts[:, 0]
                )
                area = float(_np.sum(_np.linalg.norm(cross, axis=1) / 2.0))
                stats["instances"].append(
                    {
                        "index": index,
                        "position_mm": tuple(
                            round(v, 1) for v in inst_matrix[:3, 3]
                        ),
                        "world_bbox_mm": tuple(
                            round(v, 1) for v in (bbox_max - bbox_min)
                        ),
                        "surface_area_cm2": round(area / 100.0, 2),
                        "mirrored": bool(self._safe_get(inst, "is_left_handed")),
                    }
                )
        except (ImportError, RuntimeError, ValueError, TypeError):
            stats = {}
        return stats

    def _local_stats(self: "_ChatEngine", obj: Any) -> dict[str, Any]:
        """Собирает локальные характеристики экземпляров без numpy."""
        stats: dict[str, Any] = {"instances": []}
        try:
            instances = self._safe_get(obj, "instances")
            if isinstance(instances, (list, tuple)):
                inst_list = instances
            else:
                inst_fn = getattr(obj, "instance", None)
                if not callable(inst_fn):
                    return stats
                inst_list = [inst_fn(i) for i in range(int(instances))]
            for index, inst in enumerate(inst_list):
                stats["instances"].append(
                    {
                        "index": index,
                        "offset": tuple(
                            round(v, 1) for v in self._safe_get(inst, "offset")
                        ),
                        "rotation": tuple(
                            round(v, 1) for v in self._safe_get(inst, "rotation")
                        ),
                        "scaling_factor": tuple(
                            round(v, 2) for v in self._safe_get(inst, "scaling_factor")
                        ),
                        "mirrored": bool(self._safe_get(inst, "mirror")),
                    }
                )
        except (RuntimeError, ValueError, TypeError):
            stats = {}
        return stats

    @staticmethod
    def _safe_get(target: Any, name: str) -> Any:
        """Безопасно читает атрибут или метод объекта."""
        value = getattr(target, name, None)
        if callable(value):
            try:
                value = value()
            except (TypeError, RuntimeError):
                value = None
        return value

    def _json_safe(self: "_ChatEngine", value: Any) -> Any:
        """Приводит значение к JSON-сериализуемому примитиву.

        None/bool/int/float/str возвращаются как есть; list/tuple и dict
        обрабатываются рекурсивно с ограничением размера; прочие объекты
        превращаются в строку (до 500 символов).
        """
        if value is None or isinstance(value, (bool, int, float, str)):
            return value
        if isinstance(value, (list, tuple)):
            return [self._json_safe(item) for item in list(value)[:50]]
        if isinstance(value, dict):
            return {
                str(key): self._json_safe(item)
                for key, item in list(value.items())[:50]
            }
        return str(value)[:500]

    def _collect_preset_data(self: "_ChatEngine") -> dict[str, Any]:
        """Собирает данные активных пресетов печати через preset_bundle.

        Приоритет: полный конфиг выбранного пресета (preset.config — все
        ключи и значения, включая заметки и G-code), затем full_config_value
        по списку полей, затем объединённый конфиг.
        """
        out: dict[str, Any] = {"printer": {}, "filament": {}, "print": {}}
        if orca is None:
            return out
        try:
            bundle = orca.host.preset_bundle()
            has_full_value = callable(getattr(bundle, "full_config_value", None))
            for key, (collection_attr, fields) in PRESET_SECTIONS.items():
                section: dict[str, Any] = {}
                try:
                    collection = getattr(bundle, collection_attr, None)
                    if collection is not None:
                        name = self._safe_get(collection, "get_selected_preset_name")
                        if name:
                            section["name"] = str(name)
                        # Полный конфиг выбранного пресета: все ключи и значения.
                        preset = self._safe_get(collection, "get_selected_preset")
                        if preset is not None:
                            config = getattr(preset, "config", None)
                            items = getattr(config, "items", None)
                            if callable(items):
                                result = items()
                                if isinstance(result, dict):
                                    for fkey, fval in result.items():
                                        fval = getattr(fval, "value", fval)
                                        if fval not in (None, ""):
                                            section[str(fkey)] = self._json_safe(fval)
                            elif isinstance(config, dict):
                                for fkey, fval in config.items():
                                    fval = getattr(fval, "value", fval)
                                    if fval not in (None, ""):
                                        section[str(fkey)] = self._json_safe(fval)
                except (AttributeError, RuntimeError):
                    pass
                # Fallback: если полный конфиг не получен — по списку полей.
                if len(section) <= 1:
                    for field in fields:
                        value: Any = None
                        if has_full_value:
                            try:
                                value = bundle.full_config_value(field)
                            except (RuntimeError, TypeError, ValueError):
                                value = None
                            value = getattr(value, "value", value)
                        if value in (None, ""):
                            value = self._fallback_preset_value(bundle, field)
                        if value not in (None, ""):
                            section[field] = self._json_safe(value)
                out[key] = section
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать данные пресетов: %s", exc)
            out = {"printer": {}, "filament": {}, "print": {}}
        return out

    def _fallback_preset_value(self: "_ChatEngine", bundle: Any, key: str) -> Any:
        """Ищет значение ключа через объединённый конфиг пресетов."""
        for attr in ("full_config", "full_fff_config"):
            config = self._safe_get(bundle, attr)
            if config is None:
                continue
            for accessor in ("opt_string", "get", "opt", "at", "option"):
                fn = getattr(config, accessor, None)
                if not callable(fn):
                    continue
                try:
                    value = fn(key)
                except (TypeError, RuntimeError, ValueError):
                    continue
                value = getattr(value, "value", value)
                if value not in (None, ""):
                    return value
        return None

    def _build_system_prompt(self: "_ChatEngine", ctx: dict[str, Any], include_data: bool = True) -> str:
        """Собирает системный промпт с данными контекста слайсера.

        При include_data=False возвращается только персона, заметки и
        окружение — без JSON-данных (используется командой /context,
        которая выводит данные отдельным блоком).
        """
        parts = [SYSTEM_PROMPT]
        notes = str(self._config.get("notes", "")).strip()
        if notes:
            parts.append(self._t("prompt.notes", notes=notes))
        if include_data:
            if ctx.get("model"):
                parts.append(
                    self._t(
                        "prompt.model_data",
                        data=json.dumps(ctx["model"], ensure_ascii=False, indent=2),
                    )
                )
            if ctx.get("presets"):
                parts.append(
                    self._t(
                        "prompt.print_profiles",
                        data=json.dumps(ctx["presets"], ensure_ascii=False, indent=2),
                    )
                )
        parts.append(
            self._t(
                "prompt.environment",
                ver=sys.version.split()[0],
                time=time.strftime("%Y-%m-%d %H:%M"),
            )
        )
        return "\n\n".join(parts)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Грубо оценивает число токенов в тексте."""
        return len(text) // 4

    def _estimate_context_tokens(self: "_ChatEngine", flags: dict[str, Any]) -> int:
        """Оценивает число токенов контекста по флагам."""
        try:
            ctx = self._collect_context(flags)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать контекст слайсера: %s", exc)
            ctx = {}
        return self._estimate_tokens(json.dumps(ctx, ensure_ascii=False))
