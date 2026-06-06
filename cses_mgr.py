"""
CSES schedule import/export support.

The bundled pycses version still targets the old CSES shape.  This converter
keeps the public Class Widgets API intact while reading and writing both:

- CSES v1: schedules use enable_day + weeks.
- CSES v2: schedules use enable_day arrays and configuration.cycle.
"""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple, Union

import yaml
from loguru import logger

import list_
from basic_dirs import CW_HOME
from file import config_center

CSES_WEEKS_TEXTS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
CSES_WEEKS = [1, 2, 3, 4, 5, 6, 7]
CW_DAYS = [str(day) for day in range(7)]
UNSET_SUBJECT = "\u672a\u6dfb\u52a0"

DEFAULT_V2_CYCLE = {
    "work_count": 10,
    "rest_count": 4,
    "spans": [
        {"activity": "work", "count": 5},
        {"activity": "rest", "count": 2},
        {"activity": "work", "count": 5},
        {"activity": "rest", "count": 2},
    ],
}


def _get_time(time: Union[str, int]) -> datetime:
    if isinstance(time, int):
        return datetime.strptime(
            f'{int(time / 60 / 60)}:{int(time / 60 % 60)}:{time % 60}', '%H:%M:%S'
        )
    if isinstance(time, str):
        for fmt in ('%H:%M:%S', '%H:%M'):
            try:
                return datetime.strptime(time, fmt)
            except ValueError:
                continue
    raise ValueError(f'Need int seconds or HH:MM[:SS], got {type(time)}: {time!r}')


def _time_text(time: datetime) -> str:
    return time.strftime('%H:%M:%S')


def _empty_day_map() -> Dict[str, List[Any]]:
    return {day: [] for day in CW_DAYS}


def _empty_timeline_map() -> Dict[str, List[Any]]:
    return {"default": [], **_empty_day_map()}


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _configured_cses_version() -> int:
    try:
        version = int(config_center.read_conf('Version', 'cses_version'))
    except Exception:
        version = 1
    return 2 if version == 2 else 1


def _alt_schedule_enabled() -> bool:
    try:
        return config_center.read_conf('General', 'enable_alt_schedule') == '1'
    except Exception:
        return False


def _load_yaml(path: Union[str, Path]) -> Dict[str, Any]:
    with open(path, encoding='utf-8') as file:
        data = yaml.safe_load(file) or {}
    if not isinstance(data, dict):
        raise ValueError("CSES root must be a mapping")
    return data


def _normalize_classes(classes: Iterable[Dict[str, Any]]) -> List[Dict[str, str]]:
    normalized = []
    for class_ in classes or []:
        if not isinstance(class_, dict):
            continue
        subject = str(class_.get('subject') or '').strip()
        if not subject:
            continue
        try:
            start_time = _time_text(_get_time(class_.get('start_time')))
            end_time = _time_text(_get_time(class_.get('end_time')))
        except ValueError:
            logger.warning(f"Skip CSES class with invalid time: {class_}")
            continue
        if _get_time(end_time) <= _get_time(start_time):
            logger.warning(f"Skip CSES class with invalid time range: {class_}")
            continue
        normalized.append(
            {
                "subject": subject,
                "start_time": start_time,
                "end_time": end_time,
            }
        )
    normalized.sort(key=lambda item: _get_time(item["start_time"]))
    return normalized

def _ensure_cw_shape(data: Dict[str, Any]) -> Dict[str, Any]:
    data.setdefault("part", {})
    data.setdefault("part_name", {})
    data.setdefault("timeline", _empty_timeline_map())
    data.setdefault("timeline_even", _empty_timeline_map())
    data.setdefault("schedule", _empty_day_map())
    data.setdefault("schedule_even", _empty_day_map())
    data.setdefault("url", "local")

    for key in ("timeline", "timeline_even"):
        if not isinstance(data.get(key), dict):
            data[key] = _empty_timeline_map()
        data[key].setdefault("default", [])
        for day in CW_DAYS:
            data[key].setdefault(day, [])

    for key in ("schedule", "schedule_even"):
        if not isinstance(data.get(key), dict):
            data[key] = _empty_day_map()
        for day in CW_DAYS:
            data[key].setdefault(day, [])

    for part_key, part_value in list(data["part"].items()):
        if isinstance(part_value, (list, tuple)) and len(part_value) == 2:
            data["part"][part_key] = [part_value[0], part_value[1], "part"]

    return data


def _build_part_registry(cw_data: Dict[str, Any]) -> Tuple[Dict[Tuple[int, int], str], int]:
    registry: Dict[Tuple[int, int], str] = {}
    next_index = 0
    for key, value in cw_data.get("part", {}).items():
        try:
            hour, minute = int(value[0]), int(value[1])
        except (TypeError, ValueError, IndexError):
            continue
        registry[(hour, minute)] = str(key)
        next_index = max(next_index, _as_int(key, -1) + 1)
    return registry, next_index


def _v1_days(raw_day: Any) -> List[str]:
    if isinstance(raw_day, list):
        days: List[str] = []
        for item in raw_day:
            days.extend(_v1_days(item))
        return days

    if isinstance(raw_day, int):
        if raw_day in CSES_WEEKS:
            return [str(CSES_WEEKS.index(raw_day))]
        if 0 <= raw_day <= 6:
            return [str(raw_day)]
        return []

    if isinstance(raw_day, str):
        text = raw_day.strip().lower()
        aliases = {
            "mon": 0,
            "monday": 0,
            "tue": 1,
            "tuesday": 1,
            "wed": 2,
            "wednesday": 2,
            "thu": 3,
            "thursday": 3,
            "fri": 4,
            "friday": 4,
            "sat": 5,
            "saturday": 5,
            "sun": 6,
            "sunday": 6,
        }
        if text in aliases:
            return [str(aliases[text])]
        if text.isdigit():
            return _v1_days(int(text))

    return []


def _week_types(raw_weeks: Any) -> List[str]:
    weeks = str(raw_weeks or "all").strip().lower()
    if weeks == "odd":
        return ["odd"]
    if weeks == "even":
        return ["even"]
    return ["odd", "even"]


def _v2_workday_positions(configuration: Dict[str, Any]) -> Dict[int, int]:
    cycle = configuration.get("cycle") if isinstance(configuration, dict) else None
    if not isinstance(cycle, dict):
        cycle = DEFAULT_V2_CYCLE
    spans = cycle.get("spans")
    if not isinstance(spans, list):
        spans = DEFAULT_V2_CYCLE["spans"]

    positions: Dict[int, int] = {}
    calendar_day = 0
    work_day = 0
    for span in spans:
        if not isinstance(span, dict):
            continue
        activity = span.get("activity")
        count = max(0, _as_int(span.get("count")))
        for _ in range(count):
            calendar_day += 1
            if activity == "work":
                work_day += 1
                positions[work_day] = calendar_day
    return positions


def _v2_targets(raw_enable_day: Any, configuration: Dict[str, Any]) -> List[Tuple[str, str]]:
    raw_days = raw_enable_day if isinstance(raw_enable_day, list) else [raw_enable_day]
    positions = _v2_workday_positions(configuration)
    targets: List[Tuple[str, str]] = []

    for raw_day in raw_days:
        work_day = _as_int(raw_day)
        if work_day <= 0:
            continue
        calendar_position = positions.get(work_day, work_day)
        day = str((calendar_position - 1) % 7)
        week_type = "even" if ((calendar_position - 1) // 7) % 2 else "odd"
        targets.append((week_type, day))

    return targets


def _make_timeline_from_classes(
    cw_data: Dict[str, Any],
    classes: List[Dict[str, str]],
    part_registry: Dict[Tuple[int, int], str],
    next_part_index: int,
) -> Tuple[List[List[Any]], List[str], int]:
    if not classes:
        return [], [], next_part_index

    first_start = _get_time(classes[0]["start_time"])
    part_key = (first_start.hour, first_start.minute)
    part_index = part_registry.get(part_key)
    if part_index is None:
        part_index = str(next_part_index)
        next_part_index += 1
        part_registry[part_key] = part_index
        cw_data["part"][part_index] = [first_start.hour, first_start.minute, "part"]
        cw_data["part_name"][part_index] = f"Part {part_index}"

    timeline: List[List[Any]] = []
    subjects: List[str] = []
    last_end_time: Optional[datetime] = None

    for index, class_ in enumerate(classes, start=1):
        start_time = _get_time(class_["start_time"])
        end_time = _get_time(class_["end_time"])
        if last_end_time is not None:
            gap = int((start_time - last_end_time).total_seconds() / 60)
            if gap > 0:
                timeline.append([1, part_index, index - 1, gap])
        duration = int((end_time - start_time).total_seconds() / 60)
        timeline.append([0, part_index, index, duration])
        subjects.append(class_["subject"])
        last_end_time = end_time

    return timeline, subjects, next_part_index


def _apply_cw_day(
    cw_data: Dict[str, Any],
    week_type: str,
    day: str,
    timeline: List[List[Any]],
    subjects: List[str],
) -> None:
    if day not in CW_DAYS:
        return

    schedule_key = "schedule_even" if week_type == "even" else "schedule"
    timeline_key = "timeline_even" if week_type == "even" else "timeline"

    old_subjects = cw_data[schedule_key].get(day) or []
    if old_subjects and old_subjects != subjects:
        logger.warning(
            f"CSES has multiple incompatible schedules for {week_type} day {day}; keep first one"
        )
        return

    cw_data[schedule_key][day] = list(subjects)
    cw_data[timeline_key][day] = [list(item) for item in timeline]


def _part_start_time(parts: Dict[str, Any], part: str) -> Optional[datetime]:
    value = parts.get(str(part))
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        return datetime.strptime(f'{int(value[0])}:{int(value[1])}', '%H:%M')
    except ValueError:
        return None


def _timeline_for_day(cw_data: Dict[str, Any], week_type: str, day: str) -> List[List[Any]]:
    timeline_key = "timeline_even" if week_type == "even" else "timeline"
    timeline_map = cw_data.get(timeline_key, {})
    if timeline_map.get(day):
        return timeline_map[day]
    if week_type == "even" and cw_data.get("timeline_even", {}).get("default"):
        return cw_data["timeline_even"]["default"]
    return cw_data.get("timeline", {}).get("default", [])


def _classes_from_cw_day(cw_data: Dict[str, Any], week_type: str, day: str) -> List[Dict[str, str]]:
    schedule_key = "schedule_even" if week_type == "even" else "schedule"
    subjects = cw_data.get(schedule_key, {}).get(day, [])
    if not isinstance(subjects, list):
        return []

    timeline = _timeline_for_day(cw_data, week_type, day)
    if not timeline:
        return []

    parts = cw_data.get("part", {})
    elapsed_by_part: Dict[str, int] = {}
    class_counts_by_part: Dict[str, int] = {}
    classes: List[Dict[str, str]] = []

    for unit in timeline:
        try:
            is_break, part, item_index, item_time = unit
        except (TypeError, ValueError):
            continue
        part = str(part)
        elapsed = elapsed_by_part.get(part, 0)
        duration = _as_int(item_time)
        start = _part_start_time(parts, part)
        if start is None or duration <= 0:
            continue

        if is_break:
            elapsed_by_part[part] = elapsed + duration
            continue

        current_count = class_counts_by_part.get(part, 0)
        class_counts_by_part[part] = current_count + 1

        try:
            prior_parts_count = sum(
                count for key, count in class_counts_by_part.items() if _as_int(key) < _as_int(part)
            )
            subject_index = _as_int(item_index, current_count + 1) - 1 + prior_parts_count
            subject = subjects[subject_index]
        except (IndexError, TypeError):
            continue

        if not subject or subject == UNSET_SUBJECT:
            elapsed_by_part[part] = elapsed + duration
            continue

        start_time = start + timedelta(minutes=elapsed)
        end_time = start_time + timedelta(minutes=duration)
        classes.append(
            {
                "subject": str(subject),
                "start_time": _time_text(start_time),
                "end_time": _time_text(end_time),
            }
        )
        elapsed_by_part[part] = elapsed + duration

    classes.sort(key=lambda item: _get_time(item["start_time"]))
    return classes


def _classes_for_export(
    cw_data: Dict[str, Any],
    week_type: str,
    day: str,
    alt_schedule_enabled: bool,
) -> List[Dict[str, str]]:
    classes = _classes_from_cw_day(cw_data, week_type, day)
    if week_type == "even" and not classes and not alt_schedule_enabled:
        return _classes_from_cw_day(cw_data, "odd", day)
    return classes


def _collect_subjects(cw_data: Dict[str, Any]) -> List[str]:
    subject_json = CW_HOME / "data" / "subject.json"
    subjects: List[str] = []
    try:
        with open(subject_json, encoding='utf-8') as data:
            subject_data = json.load(data)
            subjects.extend(str(item) for item in subject_data.get('subject_list', []))
    except FileNotFoundError:
        logger.warning(f'File {subject_json} not found')

    for schedule_key in ("schedule", "schedule_even"):
        for day_subjects in cw_data.get(schedule_key, {}).values():
            if not isinstance(day_subjects, list):
                continue
            subjects.extend(str(item) for item in day_subjects if item and item != UNSET_SUBJECT)

    seen = set()
    result = []
    for subject in subjects:
        if subject not in seen:
            seen.add(subject)
            result.append(subject)
    return result


def _subject_items(subjects: Iterable[str]) -> List[Dict[str, str]]:
    result: List[Dict[str, str]] = []
    for subject in subjects:
        item: Dict[str, str] = {
            "name": subject,
            "simplified_name": list_.get_subject_abbreviation(subject),
        }
        result.append(item)
    return result


def _append_schedule(
    schedules: List[Dict[str, Any]],
    name: str,
    enable_day: Any,
    classes: List[Dict[str, str]],
    weeks: Optional[str] = None,
) -> None:
    if not classes:
        return
    schedule = {
        "name": name,
        "enable_day": enable_day,
        "classes": classes,
    }
    if weeks is not None:
        schedule["weeks"] = weeks
    schedules.append(schedule)


def _export_v1_schedules(cw_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    schedules: List[Dict[str, Any]] = []
    alt_enabled = _alt_schedule_enabled()
    for day in CW_DAYS:
        odd_classes = _classes_from_cw_day(cw_data, "odd", day)
        even_classes = _classes_for_export(cw_data, "even", day, alt_enabled)
        enable_day = CSES_WEEKS[int(day)]
        day_name = CSES_WEEKS_TEXTS[int(day)]

        if odd_classes and odd_classes == even_classes:
            _append_schedule(schedules, day_name, enable_day, odd_classes, "all")
        else:
            _append_schedule(schedules, f"{day_name}_Odd", enable_day, odd_classes, "odd")
            _append_schedule(schedules, f"{day_name}_Even", enable_day, even_classes, "even")

    return schedules


def _compress_spans(mask: List[bool]) -> List[Dict[str, Any]]:
    spans: List[Dict[str, Any]] = []
    for is_work in mask:
        activity = "work" if is_work else "rest"
        if spans and spans[-1]["activity"] == activity:
            spans[-1]["count"] += 1
        else:
            spans.append({"activity": activity, "count": 1})
    return spans


def _v2_cycle_from_classes(classes_by_position: Dict[int, List[Dict[str, str]]]) -> Tuple[Dict[str, Any], Dict[int, int]]:
    mask = [bool(classes_by_position.get(position)) for position in range(1, 15)]
    if not any(mask):
        cycle = dict(DEFAULT_V2_CYCLE)
        return cycle, {}

    while mask.count(False) < 2:
        mask.append(False)
    while mask.count(True) < 2:
        mask.append(True)

    position_to_work_day: Dict[int, int] = {}
    work_day = 0
    for position, is_work in enumerate(mask, start=1):
        if is_work:
            work_day += 1
            if position <= 14:
                position_to_work_day[position] = work_day

    cycle = {
        "work_count": mask.count(True),
        "rest_count": mask.count(False),
        "spans": _compress_spans(mask),
    }
    return cycle, position_to_work_day


def _export_v2_schedules(
    cw_data: Dict[str, Any],
    position_to_work_day: Dict[int, int],
) -> List[Dict[str, Any]]:
    schedules: List[Dict[str, Any]] = []
    alt_enabled = _alt_schedule_enabled()

    for day in CW_DAYS:
        day_index = int(day)
        odd_position = day_index + 1
        even_position = day_index + 8
        odd_classes = _classes_from_cw_day(cw_data, "odd", day)
        even_classes = _classes_for_export(cw_data, "even", day, alt_enabled)
        day_name = CSES_WEEKS_TEXTS[day_index]

        if (
            odd_classes
            and odd_classes == even_classes
            and odd_position in position_to_work_day
            and even_position in position_to_work_day
        ):
            _append_schedule(
                schedules,
                day_name,
                [position_to_work_day[odd_position], position_to_work_day[even_position]],
                odd_classes,
            )
            continue

        if odd_classes and odd_position in position_to_work_day:
            _append_schedule(
                schedules,
                f"{day_name}_Odd",
                [position_to_work_day[odd_position]],
                odd_classes,
            )
        if even_classes and even_position in position_to_work_day:
            _append_schedule(
                schedules,
                f"{day_name}_Even",
                [position_to_work_day[even_position]],
                even_classes,
            )

    return schedules


class CSES_Converter:
    """
    CSES file converter used by the schedule import/export UI.
    """

    def __init__(self, path: str = './') -> None:
        self.generator: Optional[Dict[str, Any]] = None
        self.parser: Optional[Dict[str, Any]] = None
        self.path = path

    def load_parser(self) -> Union[str, Dict[str, Any]]:
        try:
            data = _load_yaml(self.path)
        except Exception as e:
            logger.error(f"CSES parser load failed: {e}")
            return "Error: Not a CSES file"

        if "version" not in data or "subjects" not in data or "schedules" not in data:
            return "Error: Not a CSES file"

        self.parser = data
        return data

    def load_generator(self) -> None:
        self.generator = {"version": _configured_cses_version()}

    def convert_to_cw(self) -> Union[Dict[str, Any], bool]:
        """
        Convert CSES v1/v2 data to the Class Widgets schedule format.
        """
        default_schedule = CW_HOME / "data" / "default_schedule.json"
        try:
            with open(default_schedule, encoding='utf-8') as file:
                cw_format = _ensure_cw_shape(json.load(file))
        except FileNotFoundError:
            logger.error(f'File {default_schedule} not found')
            return False

        if not self.parser:
            raise Exception("Parser not loaded, please load_parser() first.")

        version = _as_int(self.parser.get("version"), 1)
        configuration = self.parser.get("configuration") or {}
        schedules = self.parser.get("schedules") or []
        part_registry, next_part_index = _build_part_registry(cw_format)

        for schedule in schedules:
            if not isinstance(schedule, dict):
                continue
            classes = _normalize_classes(schedule.get("classes") or [])
            if not classes:
                continue

            timeline, subjects, next_part_index = _make_timeline_from_classes(
                cw_format,
                classes,
                part_registry,
                next_part_index,
            )

            if version == 2:
                targets = _v2_targets(schedule.get("enable_day"), configuration)
            else:
                targets = [
                    (week_type, day)
                    for week_type in _week_types(schedule.get("weeks"))
                    for day in _v1_days(schedule.get("enable_day"))
                ]

            for week_type, day in targets:
                _apply_cw_day(cw_format, week_type, day, timeline, subjects)

        return cw_format

    def convert_to_cses(
        self, cw_data: Optional[Dict[str, Any]] = None, cw_path: str = './'
    ) -> bool:
        """
        Convert Class Widgets schedule data to a CSES v1/v2 YAML file.
        """
        if not self.generator:
            raise Exception("Generator not loaded, please load_generator() first.")

        if cw_data is None:
            if cw_path == './':
                raise Exception("Please provide a path or cw_data")
            try:
                with open(cw_path, encoding='utf-8') as data:
                    cw_data = json.load(data)
            except FileNotFoundError:
                logger.error(f'File {cw_path} not found')
                return False

        cw_data = _ensure_cw_shape(cw_data)
        version = 2 if self.generator.get("version") == 2 else 1
        subjects = _subject_items(_collect_subjects(cw_data))

        if version == 2:
            alt_enabled = _alt_schedule_enabled()
            classes_by_position = {
                day + 1: _classes_from_cw_day(cw_data, "odd", str(day)) for day in range(7)
            }
            classes_by_position.update(
                {
                    day + 8: _classes_for_export(cw_data, "even", str(day), alt_enabled)
                    for day in range(7)
                }
            )
            cycle, position_to_work_day = _v2_cycle_from_classes(classes_by_position)
            cses_data = {
                "version": 2,
                "configuration": {
                    "name": Path(cw_path).stem if cw_path != './' else Path(self.path).stem,
                    "description": "Exported from Class Widgets",
                    "cycle": cycle,
                },
                "subjects": subjects,
                "schedules": _export_v2_schedules(cw_data, position_to_work_day),
            }
        else:
            cses_data = {
                "version": 1,
                "subjects": subjects,
                "schedules": _export_v1_schedules(cw_data),
            }

        try:
            with open(self.path, 'w', encoding='utf-8') as file:
                yaml.dump(cses_data, file, default_flow_style=False, allow_unicode=True, sort_keys=False)
            return True
        except Exception as e:
            logger.error(f'Error: {e}')
            return False


if __name__ == '__main__':
    importer = CSES_Converter(path='./config/cses_schedule/test.yaml')
    importer.load_parser()
    importer.convert_to_cw()

    exporter = CSES_Converter(path='./config/cses_schedule/test2.yaml')
    exporter.load_generator()
    exporter.convert_to_cses(cw_path='./config/schedule/default (3).json')
