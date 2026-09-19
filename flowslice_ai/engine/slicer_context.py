"""Контекст слайсера и оценка токенов движка FlowSlice AI.

Миксин SlicerContextMixin собирает данные о модели на столе (через
orca.host.model()), активных пресетах печати (orca.host.preset_bundle()),
строит системный промпт и оценивает размер контекста в токенах.
"""
# pyright (миксины _ChatEngine): reportGeneralTypeIssues отключён только здесь.
# pyright: reportGeneralTypeIssues=false
# pylint: disable=too-many-lines,too-many-statements,too-many-branches,broad-exception-caught
# pylint: disable=too-many-locals,too-many-nested-blocks,too-many-public-methods,too-few-public-methods

import json
import time
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from flowslice_ai.engine import _ChatEngine

try:
    import orca
except ImportError:
    orca = None  # type: ignore[assignment]

from flowslice_ai.constants import (
    FILE_ATTACHMENT_HINT,
    IMAGE_ANALYSIS_HINT,
    MAX_CONTEXT_CHARS,
    NO_VISION_HINT,
    PARAMETER_NAMING_HINT,
    PRESET_DATA_NOTE,
    SLICER_DATA_HINT,
    SYSTEM_PROMPT,
)
from flowslice_ai.logging import _LOGGER
from flowslice_ai.orca_compat import _HAS_NUMPY, _np
from flowslice_ai.setting_labels import humanize_presets
from flowslice_ai.slicer_context import is_sensitive_preset_key
from flowslice_ai.slicer_context import (
    AMBIGUOUS_PRESET_KEYS,
    PRESET_METADATA_KEYS,
    PRESET_SECTIONS,
)


class SlicerContextMixin:
    """Сбор контекста слайсера, системный промпт и оценка токенов."""

    # Небольшой TTL-кэш: сбор контекста дорогой и вызывается при каждом
    # переключении флагов и старте генерации.
    _CONTEXT_CACHE_TTL = 5.0

    def _collect_context(
        self: "_ChatEngine", flags: dict[str, Any], modes: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Собирает контекст слайсера по включённым флагам.

        modes задаёт режим выгрузки для каждого раздела пресетов
        ("changed" — только изменённые параметры, "all" — полный профиль).
        Результат кэшируется на _CONTEXT_CACHE_TTL секунд по комбинации
        флагов и режимов, чтобы не дёргать слайсер повторно.
        """
        cache_key = (
            json.dumps(flags, sort_keys=True, default=str),
            json.dumps(modes or {}, sort_keys=True, default=str),
        )
        now = time.monotonic()
        with self._context_lock:
            cache = getattr(self, "_context_cache", None)
            if not isinstance(cache, dict):
                cache = {}
                self._context_cache = cache
            cached = cache.get(cache_key)
            if isinstance(cached, tuple) and now - cached[0] < self._CONTEXT_CACHE_TTL:
                return cached[1]
        ctx = self._collect_context_uncached(flags, modes)
        with self._context_lock:
            cache.clear()
            cache[cache_key] = (now, ctx)
        return ctx

    def _collect_context_uncached(
        self: "_ChatEngine", flags: dict[str, Any], modes: dict[str, Any] | None = None
    ) -> dict[str, Any]:
        """Собирает контекст слайсера без кэширования."""
        ctx: dict[str, Any] = {}
        if flags.get("model"):
            mode_map = modes if isinstance(modes, dict) else {}
            raw_mode = mode_map.get("model")
            model_mode = raw_mode if raw_mode in ("brief", "full", "deep") else "full"
            ctx["model"] = self._collect_model_data(model_mode)
        if flags.get("filament") or flags.get("printer") or flags.get("print"):
            ctx["presets"] = self._collect_preset_data(modes, flags)
        return ctx

    def _collect_model_data(self: "_ChatEngine", mode: str = "full") -> dict[str, Any]:
        """Собирает данные о модели на столе слайсера.

        mode="full" — подробно по каждому объекту (размеры, объём, треугольники,
        мировые характеристики экземпляров); mode="deep" — то же плюс глубинные
        метрики геометрии (площадь основания, нависания, заполнение габарита);
        mode="brief" — только сводка по всей сцене: количество объектов и
        суммарные габариты/объём.
        """
        if mode == "brief":
            return self._collect_model_brief()
        deep = mode == "deep"
        data: dict[str, Any] = {
            "objects": [],
            "coords": "world",
            "deep": deep and _HAS_NUMPY,
        }
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
                        entry.update(self._world_stats(obj, vol, mesh, deep=deep))
                    else:
                        entry["coords"] = "local"
                        entry.update(self._local_stats(obj))
                    data["objects"].append(entry)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать данные модели: %s", exc, exc_info=True)
            data["objects"] = []
        return data

    def _collect_model_brief(self: "_ChatEngine") -> dict[str, Any]:
        """Собирает краткую сводку по модели на столе без деталей по объектам."""
        data: dict[str, Any] = {
            "objects_count": 0,
            "volume_cm3": 0.0,
            "triangles": 0,
            "manifold": True,
            "overall_bbox_mm": (),
            "coords": "world",
        }
        if orca is None:
            return data
        mins: list[float] = []
        maxs: list[float] = []
        count = 0
        volume_total = 0.0
        triangles = 0
        manifold = True
        try:
            model = orca.host.model()
            for obj in model.objects():
                for vol in obj.volumes():
                    mesh = self._safe_get(vol, "mesh")
                    if mesh is None:
                        continue
                    count += 1
                    bbox = self._safe_get(mesh, "bounding_box")
                    low = self._bbox_tuple(bbox, "min")
                    high = self._bbox_tuple(bbox, "max")
                    if len(low) >= 3 and len(high) >= 3:
                        if not mins:
                            mins = [float(v) for v in low[:3]]
                            maxs = [float(v) for v in high[:3]]
                        else:
                            for axis in range(3):
                                mins[axis] = min(mins[axis], float(low[axis]))
                                maxs[axis] = max(maxs[axis], float(high[axis]))
                    volume = self._safe_get(mesh, "volume")
                    if volume:
                        volume_total += float(volume) / 1000.0
                    triangles += int(self._safe_get(mesh, "triangle_count") or 0)
                    if not self._safe_get(mesh, "is_manifold"):
                        manifold = False
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать сводку модели: %s", exc, exc_info=True)
        data["objects_count"] = count
        data["volume_cm3"] = round(volume_total, 2)
        data["triangles"] = triangles
        data["manifold"] = manifold
        if mins and maxs:
            data["overall_bbox_mm"] = tuple(
                round(maxs[axis] - mins[axis], 1) for axis in range(3)
            )
            data["overall_bbox_min_mm"] = tuple(round(v, 1) for v in mins)
            data["overall_bbox_max_mm"] = tuple(round(v, 1) for v in maxs)
        return data

    def _world_stats(
        self: "_ChatEngine", obj: Any, vol: Any, mesh: Any, deep: bool = False
    ) -> dict[str, Any]:
        """Считает мировые характеристики экземпляров через numpy.

        При deep=True к каждому экземпляру добавляются глубинные метрики:
        высота, площадь основания, площадь нависаний и заполнение габарита.
        """
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
                norm = _np.linalg.norm(cross, axis=1)
                area = float(_np.sum(norm) / 2.0)
                entry: dict[str, Any] = {
                    "index": index,
                    "position_mm": tuple(round(v, 1) for v in inst_matrix[:3, 3]),
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
                if deep:
                    entry.update(
                        self._deep_instance_stats(bbox_min, bbox_max, tri_pts, cross, norm, mesh)
                    )
                stats["instances"].append(entry)
        except (ImportError, RuntimeError, ValueError, TypeError) as exc:
            _LOGGER.warning(
                "Не удалось вычислить геометрию экземпляров: %s", exc, exc_info=True
            )
            stats = {}
        return stats

    def _deep_instance_stats(
        self: "_ChatEngine",
        bbox_min: Any,
        bbox_max: Any,
        tri_pts: Any,
        cross: Any,
        norm: Any,
        mesh: Any,
    ) -> dict[str, Any]:
        """Вычисляет глубинные метрики геометрии одного экземпляра.

        Основание — треугольники, ближайшие к нижней плоскости (допуск 0.2 мм).
        Нависания — треугольники с направленной вниз нормалью круче 45°;
        основание из них исключается. Направление нормалей наружу определяется
        приближённо — по стороне от центроида меша. Нормали строятся из
        векторного произведения сторон.
        """
        assert _np is not None
        result: dict[str, Any] = {}
        try:
            safe_norm = _np.where(norm > 1e-9, norm, 1.0)
            areas = norm / 2.0
            z_min = float(_np.min(tri_pts[:, :, 2]))
            z_max = float(_np.max(tri_pts[:, :, 2]))
            tri_max_z = _np.max(tri_pts[:, :, 2], axis=1)
            base_mask = tri_max_z <= z_min + 0.2
            base_area = float(_np.sum(areas[base_mask]))
            centroids = _np.mean(tri_pts, axis=1)
            weights = areas / max(float(_np.sum(areas)), 1e-12)
            mesh_center = _np.sum(centroids * weights[:, None], axis=0)
            signs = _np.sign(_np.sum(cross * (centroids - mesh_center), axis=1))
            signs[signs == 0] = 1.0
            outward_z = (cross[:, 2] * signs) / safe_norm
            overhang_mask = (outward_z <= -0.7071) & (~base_mask)
            overhang_area = float(_np.sum(areas[overhang_mask]))
            result["height_mm"] = round(z_max - z_min, 1)
            result["base_area_cm2"] = round(base_area / 100.0, 2)
            result["overhang_area_cm2"] = round(overhang_area / 100.0, 2)
            bbox_size = _np.asarray(bbox_max) - _np.asarray(bbox_min)
            bbox_volume = float(_np.prod(bbox_size))
            mesh_volume = self._safe_get(mesh, "volume")
            if bbox_volume > 1e-6 and mesh_volume:
                result["bbox_fill_ratio"] = round(
                    float(mesh_volume) / bbox_volume, 3
                )
        except (RuntimeError, ValueError, TypeError, ZeroDivisionError) as exc:
            _LOGGER.warning(
                "Не удалось вычислить глубокие метрики экземпляра: %s", exc, exc_info=True
            )
            result = {}
        return result

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
        except (RuntimeError, ValueError, TypeError) as exc:
            _LOGGER.warning(
                "Не удалось собрать локальные характеристики модели: %s", exc, exc_info=True
            )
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
        self: "_ChatEngine",
        modes: dict[str, Any] | None = None,
        flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        """Собирает данные активных пресетов печати через preset_bundle.

        Для каждого раздела строится цепочка наследования (inherits) от корня
        к выбранному пресету. Режим выбирается отдельно для каждого раздела
        через modes: "all" — все параметры, "changed" — только изменённые
        (по умолчанию). Поле "changed" в вывод не попадает. Разделы, выключенные
        в flags ("filament"/"printer"/"print"), в результат не попадают.
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
            flag_map = flags if isinstance(flags, dict) else {}
            out: dict[str, Any] = {}
            for key, (collection_attr, fields) in PRESET_SECTIONS.items():
                if flag_map and not flag_map.get(key, True):
                    continue
                mode = "all" if mode_map.get(key) == "all" else "changed"
                out[key] = self._collect_preset_section(
                    bundle, collection_attr, fields, has_full_value, mode
                )
            return out
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning("Не удалось собрать данные пресетов: %s", exc, exc_info=True)
            return empty

    def _collect_preset_section(
        self: "_ChatEngine",
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
            # Собственные параметры выбранного пресета. В разных сборках Orca
            # preset.config может быть как списком изменений, так и уже
            # разрешённым конфигом, поэтому ниже вычисляем разницу с предками.
            selected = self._preset_config_items(preset)
            # Полный конфиг: merge по цепочке в обратном порядке (от корня),
            # значения текущего пресета перекрывают унаследованные.
            full: dict[str, Any] = {}
            for item in reversed(chain):
                for fkey, fval in self._preset_config_items(item).items():
                    full[fkey] = fval
            # Разрешённый конфиг предков (вся цепочка без выбранного пресета).
            parent_full: dict[str, Any] = {}
            for item in reversed(chain[1:]):
                for fkey, fval in self._preset_config_items(item).items():
                    parent_full[fkey] = fval
            # Изменённые: собственные ключи выбранного пресета, значения которых
            # отличаются от разрешённого конфига предков.
            changed = {
                fkey: fval
                for fkey, fval in selected.items()
                if parent_full.get(fkey) != fval
            }
            params = {
                fkey: self._json_safe(fval)
                for fkey, fval in (full if mode == "all" else changed).items()
            }
            # Уточняем значения по объединённому конфигу Orca: он отдаёт
            # уже разрешённые значения (с учётом наследования и вычислений).
            if has_full_value:
                for fkey in list(params):
                    # Ключи, общие для нескольких разделов, merged-конфиг не
                    # различает — оставляем значение из собственного профиля.
                    if fkey in AMBIGUOUS_PRESET_KEYS:
                        continue
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
                    if has_full_value and field not in AMBIGUOUS_PRESET_KEYS:
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
        safe: dict[str, Any] = {}
        secret_keys: list[str] = []
        for fkey, fval in result.items():
            if fkey in PRESET_METADATA_KEYS:
                continue
            if is_sensitive_preset_key(fkey):
                secret_keys.append(fkey)
                continue
            safe[fkey] = fval
        if secret_keys:
            _LOGGER.debug(
                "Из данных профиля исключены чувствительные параметры (%d): %s",
                len(secret_keys),
                ", ".join(sorted(secret_keys)),
            )
        return safe

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

    def _build_system_prompt(
        self: "_ChatEngine",
        ctx: dict[str, Any],
        include_data: bool = True,
        has_images: bool = False,
        no_vision: bool = False,
        has_files: bool = False,
    ) -> str:
        """Собирает системный промпт с данными контекста слайсера.

        Промпт модульный: блоки добавляются только по необходимости, чтобы не
        тратить токены на неактуальные инструкции. При include_data=False
        возвращается только персона, язык, заметки и данные — без JSON-данных
        слайсера (используется командой /context, которая выводит данные
        отдельным блоком). При has_images=True добавляются правила анализа
        изображений дефектов печати, при no_vision=True — требование честно
        сообщить об отсутствии зрения. При has_files=True — пояснение формата
        <document>, при наличии профилей — правила именования параметров.
        """
        parts = [SYSTEM_PROMPT]
        if has_images:
            parts.append(IMAGE_ANALYSIS_HINT)
        if no_vision:
            parts.append(NO_VISION_HINT)
        notes = str(self._config.get("notes", "")).strip()
        if notes:
            parts.append(self._t("prompt.notes", notes=notes))
        has_model = bool(ctx.get("model"))
        has_presets = bool(ctx.get("presets"))
        if include_data:
            if has_model or has_presets:
                parts.append(SLICER_DATA_HINT)
            if has_model:
                parts.append(
                    self._t(
                        "prompt.model_data",
                        data=json.dumps(ctx["model"], ensure_ascii=False, indent=2),
                    )
                )
            if has_presets:
                lang = (
                    self._config.get("language", "en")
                    if isinstance(self._config, dict)
                    else "en"
                )
                # Ключи пресетов заменяются на «Метка в интерфейсе (внутренний id)»,
                # чтобы модель называла параметры человекочитаемо.
                parts.append(PARAMETER_NAMING_HINT)
                presets = humanize_presets(ctx["presets"], str(lang))
                parts.append(
                    self._t(
                        "prompt.print_profiles",
                        data=json.dumps(presets, ensure_ascii=False, indent=2),
                        data_note=PRESET_DATA_NOTE,
                    )
                )
        if has_files:
            parts.append(FILE_ATTACHMENT_HINT)
        # Язык ответа — последним: инструкция стоит в конце системного промпта,
        # сразу перед сообщением пользователя, и модель реже переключается
        # на английский из-за англоязычных данных и подсказок выше.
        parts.append(self._t("prompt.language"))
        return "\n\n".join(parts)

    @staticmethod
    def _estimate_tokens(text: str) -> int:
        """Грубо оценивает число токенов в тексте."""
        return len(text) // 4

    def _estimate_context_tokens(
        self: "_ChatEngine", flags: dict[str, Any], modes: dict[str, Any] | None = None
    ) -> int:
        """Оценивает реальный объём контекста (промпт + история) в токенах.

        Считается именно то, что уйдёт в модель: системный промпт со всеми
        выбранными данными слайсера и история чата (при флаге history).
        Тексты изображений (data URI) не учитываются — их токены считает
        провайдер отдельно.
        """
        try:
            ctx = self._collect_context(flags, modes)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Не удалось собрать контекст слайсера: %s", exc, exc_info=True
            )
            ctx = {}
        try:
            system = self._build_system_prompt(ctx)
        except Exception as exc:  # noqa: BLE001
            _LOGGER.warning(
                "Не удалось собрать системный промпт: %s", exc, exc_info=True
            )
            system = SYSTEM_PROMPT
        chunks = [system]
        if flags.get("history"):
            chat = self._active_chat()
            if chat is not None:
                summary = str(chat.get("summary", "") or "").strip()
                if summary:
                    chunks.append(self._t("compact.summary_header") + summary)
                for msg in self._history_messages(chat, MAX_CONTEXT_CHARS):
                    text = self._message_text(msg)
                    if text:
                        chunks.append(text)
        return self._estimate_tokens("".join(chunks))

    @staticmethod
    def _message_text(msg: dict[str, Any]) -> str:
        """Возвращает текстовую часть сообщения, пропуская изображения."""
        content = msg.get("content")
        if isinstance(content, str):
            return content
        parts: list[str] = []
        if isinstance(content, list):
            for block in content:
                if isinstance(block, dict) and isinstance(block.get("text"), str):
                    parts.append(block["text"])
        return "".join(parts)
