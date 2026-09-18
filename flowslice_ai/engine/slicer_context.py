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
from flowslice_ai.slicer_context import PRESET_METADATA_KEYS, PRESET_SECTIONS


class SlicerContextMixin:
    """Сбор контекста слайсера, системный промпт и оценка токенов."""

    def _collect_context(
        self: "_ChatEngine", flags: dict[str, Any], modes: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Собирает контекст слайсера по включённым флагам.

        modes задаёт режим выгрузки для каждого раздела пресетов
        ("changed" — только изменённые параметры, "all" — полный профиль).
        """
        ctx: dict[str, Any] = {}
        if flags.get("model"):
            ctx["model"] = self._collect_model_data()
        if flags.get("filament") or flags.get("printer") or flags.get("print"):
            ctx["presets"] = self._collect_preset_data(modes)
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
                    local_bbox: tuple[float, ...] = ()
                    if bbox is not None:
                        size = getattr(bbox, "size", bbox)
                        if isinstance(size, (tuple, list)) and len(size) >= 3:
                            local_bbox = tuple(round(float(v), 1) for v in size[:3])
                    volume = self._safe_get(mesh, "volume")
                    entry: dict[str, Any] = {
                        "name": self._safe_get(vol, "name") or "",
                        "local_bbox_mm": local_bbox,
                        "local_bbox_min_mm": self._bbox_tuple(bbox, "min"),
                        "local_bbox_max_mm": self._bbox_tuple(bbox, "max"),
                        "local_bbox_center_mm": self._bbox_tuple(bbox, "center"),
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
                        "world_bbox_min_mm": tuple(round(v, 1) for v in bbox_min),
                        "world_bbox_max_mm": tuple(round(v, 1) for v in bbox_max),
                        "world_bbox_center_mm": tuple(
                            round(v, 1) for v in ((bbox_max + bbox_min) / 2.0)
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
    def _bbox_tuple(bbox: Any, name: str) -> tuple[float, ...]:
        """Извлекает из BoundingBox кортеж (x, y, z) по имени атрибута.

        Поддерживает как свойства, так и методы; округляет до 0.1 мм.
        При отсутствии данных возвращает пустой кортеж.
        """
        if bbox is None:
            return ()
        raw = getattr(bbox, name, None)
        if callable(raw):
            try:
                raw = raw()
            except (TypeError, RuntimeError):
                return ()
        if isinstance(raw, (tuple, list)) and len(raw) >= 3:
            return tuple(round(float(v), 1) for v in raw[:3])
        return ()

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

    def _collect_preset_data(
        self: "_ChatEngine", modes: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Собирает данные активных пресетов печати через preset_bundle.

        Для каждого раздела строится цепочка наследования (inherits) от корня
        к выбранному пресету. Режим выбирается отдельно для каждого раздела
        через modes: "all" — все параметры, "changed" — только изменённые
        (по умолчанию). Поле "changed" в вывод не попадает.
        """
        empty: dict[str, Any] = {
            "printer": {"name": "", "params": {}},
            "filament": {"name": "", "params": {}},
            "print": {"name": "", "params": {}},
        }
        if orca is None:
            return empty
        try:
            bundle = orca.host.preset_bundle()
            if bundle is None:
                return empty
            has_full_value = callable(getattr(bundle, "full_config_value", None))
            mode_map = modes if isinstance(modes, dict) else {}
            out: dict[str, Any] = {}
            for key, (collection_attr, fields) in PRESET_SECTIONS.items():
                mode = "all" if mode_map.get(key) == "all" else "changed"
                out[key] = self._collect_preset_section(
                    bundle, collection_attr, fields, has_full_value, mode
                )
            return out
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать данные пресетов: %s", exc)
            return empty

    def _collect_preset_section(
        self: "_ChatEngine",  # pyright: ignore[reportGeneralTypeIssues]
        bundle: Any,
        collection_attr: str,
        fields: tuple[str, ...],
        has_full_value: bool,
        mode: str,
    ) -> dict[str, Any]:
        """Собирает данные одного раздела пресетов в едином формате.

        Формат раздела: {"name", "params"} — имя выбранного пресета и словарь
        параметров (полных или только изменённых согласно mode).
        """
        section: dict[str, Any] = {"name": "", "params": {}}
        try:
            collection = getattr(bundle, collection_attr, None)
            if collection is None:
                return section
            name = self._safe_get(collection, "get_selected_preset_name")
            preset = self._safe_get(collection, "get_selected_preset")
            if preset is None:
                section["name"] = str(name) if name else ""
                return section
            section["name"] = str(name) if name else str(getattr(preset, "name", "") or "")
            # Цепочка наследования от корня к текущему пресету.
            chain = self._preset_inheritance_chain(collection, preset)
            # Полный конфиг: merge по цепочке в обратном порядке (от корня),
            # значения текущего пресета перекрывают унаследованные.
            full: dict[str, Any] = {}
            for item in reversed(chain):
                for fkey, fval in self._preset_config_items(item).items():
                    full[fkey] = self._json_safe(fval)
            changed = {
                fkey: self._json_safe(fval)
                for fkey, fval in self._preset_config_items(preset).items()
            }
            params = dict(full if mode == "all" else changed)
            # Уточняем значения по объединённому конфигу Orca: он отдаёт
            # уже разрешённые значения (с учётом наследования и вычислений).
            if has_full_value:
                for fkey in list(params):
                    try:
                        value = bundle.full_config_value(fkey)
                    except (RuntimeError, TypeError, ValueError):
                        continue
                    value = getattr(value, "value", value)
                    if value not in (None, ""):
                        params[fkey] = self._json_safe(value)
            # Fallback: полный конфиг раздела не собран — по списку полей.
            if not params and mode == "all":
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
                        params[field] = self._json_safe(value)
            section["params"] = params
        except (AttributeError, RuntimeError, TypeError, ValueError) as exc:
            _LOGGER.warning(
                "Не удалось собрать раздел пресетов %s: %s", collection_attr, exc
            )
        return section

    @staticmethod
    def _preset_inherits_name(preset: Any) -> str:
        """Возвращает имя родительского пресета из ключа "inherits".

        Основной путь — публичный API плагина Orca (config_value). Резервный
        путь — прямой доступ к config для совместимости со старыми сборками.
        """
        value_fn = getattr(preset, "config_value", None)
        if callable(value_fn):
            try:
                value = value_fn("inherits")
            except (TypeError, RuntimeError, ValueError):
                value = None
            value = getattr(value, "value", value)
            if value:
                return str(value)
        config = getattr(preset, "config", None)
        if isinstance(config, dict):
            return str(config.get("inherits", "") or "")
        if config is not None:
            getter = getattr(config, "get", None)
            if callable(getter):
                try:
                    return str(getter("inherits") or "")
                except (TypeError, RuntimeError, ValueError):
                    return ""
        return ""

    @staticmethod
    def _preset_inheritance_chain(collection: Any, preset: Any) -> list[Any]:
        """Строит цепочку наследования пресета от корня к текущему.

        Родитель берётся из ключа "inherits" конфига пресета; цепочка
        ограничена 20 шагами и защищена от циклов по именам пресетов.
        """
        chain: list[Any] = []
        seen: set[str] = set()
        cur = preset
        for _ in range(20):
            if cur is None:
                break
            cur_name = str(getattr(cur, "name", "") or "")
            if cur_name in seen:
                break
            seen.add(cur_name)
            chain.append(cur)
            parent_name = SlicerContextMixin._preset_inherits_name(cur)
            if not parent_name:
                break
            finder = getattr(collection, "find_preset", None)
            if not callable(finder):
                break
            try:
                cur = finder(parent_name)
            except (TypeError, RuntimeError, ValueError):
                break
        return chain

    @staticmethod
    def _preset_config_items(preset: Any) -> dict[str, Any]:
        """Возвращает собственные ключи пресета без metadata-ключей.

        Основной путь — публичный API плагина Orca: config_keys() возвращает
        список ключей, config_value(key) — значение. Резервный путь — прямой
        доступ к config для совместимости со старыми сборками. Пустые
        значения (None, "") отбрасываются.
        """
        result: dict[str, Any] = {}
        keys_fn = getattr(preset, "config_keys", None)
        value_fn = getattr(preset, "config_value", None)
        if callable(keys_fn) and callable(value_fn):
            try:
                raw_keys: Any = keys_fn()
                keys = list(raw_keys)
            except (TypeError, RuntimeError, ValueError):
                keys = []
            for fkey in keys:
                try:
                    fval = value_fn(str(fkey))
                except (TypeError, RuntimeError, ValueError):
                    continue
                fval = getattr(fval, "value", fval)
                if fval not in (None, ""):
                    result[str(fkey)] = fval
        if not result:
            config = getattr(preset, "config", None)
            items = getattr(config, "items", None)
            if callable(items):
                try:
                    raw: Any = items()
                except (TypeError, RuntimeError):
                    raw = None
                if isinstance(raw, dict):
                    source = raw.items()
                elif raw is not None:
                    # dict_items / прочие итерируемые пары ключ-значение.
                    try:
                        source = list(raw)
                    except TypeError:
                        source = []
                else:
                    source = []
                for fkey, fval in source:
                    fval = getattr(fval, "value", fval)
                    if fval not in (None, ""):
                        result[str(fkey)] = fval
            elif isinstance(config, dict):
                for fkey, fval in config.items():
                    fval = getattr(fval, "value", fval)
                    if fval not in (None, ""):
                        result[str(fkey)] = fval
        return {
            fkey: fval
            for fkey, fval in result.items()
            if fkey not in PRESET_METADATA_KEYS
        }

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

    def _estimate_context_tokens(
        self: "_ChatEngine", flags: dict[str, Any], modes: dict[str, Any] | None = None
    ) -> int:
        """Оценивает число токенов контекста по флагам и режимам пресетов."""
        try:
            ctx = self._collect_context(flags, modes)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать контекст слайсера: %s", exc)
            ctx = {}
        return self._estimate_tokens(json.dumps(ctx, ensure_ascii=False))
