#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
TaskScheduler — 命令行任务调度模拟器

按依赖顺序（拓扑排序）执行一组任务，模拟真实耗时与随机成败，
支持失败重试、依赖失败传播、全局超时、彩色日志与 JSON 报告。
"""

from __future__ import annotations

import argparse
import json
import os
import random
import sys
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

try:
    import yaml  # type: ignore
except ImportError:  # pragma: no cover
    yaml = None  # type: ignore


# --------------------------------------------------------------------------- #
# 常量
# --------------------------------------------------------------------------- #

MAX_ATTEMPTS = 3  # 最多尝试次数（含首次）

# 状态枚举
STATUS_SUCCESS = "SUCCESS"
STATUS_FAILED = "FAILED"
STATUS_SKIPPED = "SKIPPED"
STATUS_TIMEOUT = "TIMEOUT"
STATUS_RETRY = "RETRY"

# 控制台颜色（ANSI）
_COLOR_RESET = "\033[0m"
_COLOR_GREEN = "\033[32m"
_COLOR_RED = "\033[31m"
_COLOR_YELLOW = "\033[33m"
_COLOR_BLUE = "\033[34m"
_COLOR_GRAY = "\033[90m"

_STATUS_COLOR = {
    STATUS_SUCCESS: _COLOR_GREEN,
    STATUS_FAILED: _COLOR_RED,
    STATUS_RETRY: _COLOR_YELLOW,
    STATUS_SKIPPED: _COLOR_BLUE,
    STATUS_TIMEOUT: _COLOR_RED,
}


# --------------------------------------------------------------------------- #
# 数据结构
# --------------------------------------------------------------------------- #

@dataclass
class Task:
    name: str
    duration: float
    success_rate: float
    dependencies: List[str] = field(default_factory=list)
    # 运行时字段
    status: str = STATUS_SKIPPED
    attempts: int = 0
    started_at: Optional[float] = None
    ended_at: Optional[float] = None


# --------------------------------------------------------------------------- #
# 工具函数
# --------------------------------------------------------------------------- #

def _enable_vt_processing() -> None:
    """在 Windows 上启用 ANSI 转义序列支持。"""
    if os.name != "nt":
        return
    try:
        import ctypes
        from ctypes import wintypes
        kernel32 = ctypes.windll.kernel32
        STD_OUTPUT_HANDLE = wintypes.DWORD(-11)
        handle = kernel32.GetStdHandle(STD_OUTPUT_HANDLE)
        mode = wintypes.DWORD()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
            new_mode = mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
            kernel32.SetConsoleMode(handle, wintypes.DWORD(new_mode))
    except Exception:  # pragma: no cover - 失败则降级为无彩色
        pass


_USE_COLOR = False


def _colorize(text: str, color: str) -> str:
    if not _USE_COLOR:
        return text
    return f"{color}{text}{_COLOR_RESET}"


def log(level: str, message: str) -> None:
    """统一日志输出。level 取 INFO / SUCCESS / FAILED / RETRY / SKIPPED / TIMEOUT / WARN。"""
    color = _STATUS_COLOR.get(level, _COLOR_GRAY)
    tag = _colorize(f"[{level}]", color)
    print(f"{tag} {message}", flush=True)


def die(message: str) -> "None":
    """打印可读错误并以非 0 退出，禁止栈回溯。"""
    print(f"{_colorize('[ERROR]', _COLOR_RED)} {message}", file=sys.stderr, flush=True)
    sys.exit(1)


# --------------------------------------------------------------------------- #
# 配置加载与校验
# --------------------------------------------------------------------------- #

def load_config_safe(path: str) -> Dict[str, Any]:
    """load_config 的异常安全版本。"""
    if not os.path.isfile(path):
        die(f"配置文件不存在: {path}")

    ext = os.path.splitext(path)[1].lower()
    try:
        with open(path, "r", encoding="utf-8") as f:
            text = f.read()
    except OSError as e:
        die(f"无法读取配置文件: {path} ({e})")

    if ext in (".yaml", ".yml"):
        if yaml is None:
            die("未安装 PyYAML，无法解析 YAML 文件。请先 `pip install pyyaml`。")
        try:
            data = yaml.safe_load(text)
        except yaml.YAMLError as e:
            die(f"YAML 语法错误: {e}")
    elif ext == ".json":
        try:
            data = json.loads(text)
        except json.JSONDecodeError as e:
            die(f"JSON 语法错误: {e}")
    else:
        die(f"不支持的配置文件扩展名: {ext}（仅支持 .yaml/.yml/.json）")

    if not isinstance(data, dict):
        die("配置文件根节点必须是对象（dict）。")

    return data


def parse_tasks(data: Dict[str, Any]) -> List[Task]:
    """校验并将配置转换为 Task 列表。"""
    tasks_raw = data.get("tasks")
    if not isinstance(tasks_raw, list) or len(tasks_raw) == 0:
        die("配置中的 `tasks` 必须是非空列表。")

    tasks: List[Task] = []
    seen_names = set()
    for i, item in enumerate(tasks_raw):
        if not isinstance(item, dict):
            die(f"第 {i + 1} 个任务不是对象。")

        name = item.get("name")
        if not isinstance(name, str) or not name.strip():
            die(f"第 {i + 1} 个任务缺少合法的 `name` 字段。")
        if name in seen_names:
            die(f"任务名重复: {name}")
        seen_names.add(name)

        duration = item.get("duration")
        if not isinstance(duration, (int, float)) or isinstance(duration, bool) or duration < 0:
            die(f"任务 `{name}` 的 `duration` 必须是非负数字。")

        success_rate = item.get("success_rate")
        if (not isinstance(success_rate, (int, float))
                or isinstance(success_rate, bool)
                or success_rate < 0 or success_rate > 1):
            die(f"任务 `{name}` 的 `success_rate` 必须是 0~1 之间的数字。")

        deps = item.get("dependencies", [])
        if deps is None:
            deps = []
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            die(f"任务 `{name}` 的 `dependencies` 必须是字符串列表。")

        tasks.append(Task(
            name=name,
            duration=float(duration),
            success_rate=float(success_rate),
            dependencies=list(deps),
        ))

    # 检查依赖是否都存在
    name_set = {t.name for t in tasks}
    for t in tasks:
        for d in t.dependencies:
            if d not in name_set:
                die(f"任务 `{t.name}` 依赖了不存在的任务: {d}")

    return tasks


# --------------------------------------------------------------------------- #
# 拓扑排序（Kahn 算法，检测环）
# --------------------------------------------------------------------------- #

def topo_sort(tasks: List[Task]) -> List[Task]:
    """返回拓扑排序后的任务列表；若存在依赖环则退出。"""
    name_to_task = {t.name: t for t in tasks}
    in_degree = {t.name: len(t.dependencies) for t in tasks}
    # 反向邻接表：dep -> [依赖它的任务]
    dependents: Dict[str, List[str]] = {t.name: [] for t in tasks}
    for t in tasks:
        for d in t.dependencies:
            dependents[d].append(t.name)

    queue = [t.name for t in tasks if in_degree[t.name] == 0]
    order: List[str] = []
    while queue:
        # 保持稳定：按任务在原列表中的顺序取出，使结果可预测
        queue.sort(key=lambda n: next(i for i, x in enumerate(tasks) if x.name == n))
        cur = queue.pop(0)
        order.append(cur)
        for nxt in dependents[cur]:
            in_degree[nxt] -= 1
            if in_degree[nxt] == 0:
                queue.append(nxt)

    if len(order) != len(tasks):
        cycle_nodes = [t.name for t in tasks if t.name not in order]
        die(f"检测到依赖环，涉及任务: {', '.join(cycle_nodes)}")

    return [name_to_task[n] for n in order]


# --------------------------------------------------------------------------- #
# 调度执行
# --------------------------------------------------------------------------- #

def run_scheduler(tasks: List[Task], timeout: Optional[float], rng: random.Random) -> Dict[str, Any]:
    """执行调度，返回报告数据。"""
    start_time = time.time()
    timed_out = False

    # 预计算每个任务的依赖状态查询
    name_to_task = {t.name: t for t in tasks}

    def elapsed() -> float:
        return time.time() - start_time

    def timed_out_now() -> bool:
        if timeout is None:
            return False
        return elapsed() >= timeout

    for task in tasks:
        # 超时：剩余所有任务标记为 TIMEOUT
        if timed_out:
            task.status = STATUS_TIMEOUT
            task.attempts = 0
            continue

        # 若超时已到，则当前任务也标记 TIMEOUT
        if timed_out_now():
            timed_out = True
            task.status = STATUS_TIMEOUT
            task.attempts = 0
            log("TIMEOUT", f"全局超时（{timeout:.2f}s），终止任务 `{task.name}`。")
            continue

        # 检查依赖：任何依赖非 SUCCESS，则跳过
        failed_deps = []
        for d in task.dependencies:
            dep_task = name_to_task[d]
            if dep_task.status != STATUS_SUCCESS:
                failed_deps.append((d, dep_task.status))
        if failed_deps:
            task.status = STATUS_SKIPPED
            task.attempts = 0
            deps_str = ", ".join(f"{d}({s})" for d, s in failed_deps)
            log("SKIPPED", f"任务 `{task.name}` 因依赖未成功而跳过（{deps_str}）。")
            continue

        # 执行任务
        task.started_at = time.time()
        success = False
        for attempt in range(1, MAX_ATTEMPTS + 1):
            task.attempts = attempt
            # 执行前再次检查超时
            if timed_out_now():
                timed_out = True
                task.status = STATUS_TIMEOUT
                log("TIMEOUT", f"任务 `{task.name}` 第 {attempt} 次尝试前触发超时。")
                break

            log("INFO", f"任务 `{task.name}` 开始执行（第 {attempt} 次尝试，"
                        f"预计耗时 {task.duration:.2f}s）。")
            # 模拟耗时
            time.sleep(task.duration)

            # sleep 后检查超时
            if timed_out_now():
                timed_out = True
                task.status = STATUS_TIMEOUT
                log("TIMEOUT", f"任务 `{task.name}` 执行耗时超出全局超时（{timeout:.2f}s）。")
                break

            # 判定成败
            if rng.random() < task.success_rate:
                success = True
                break
            else:
                if attempt < MAX_ATTEMPTS:
                    log("RETRY", f"任务 `{task.name}` 第 {attempt} 次尝试失败，准备重试。")
                else:
                    log("FAILED", f"任务 `{task.name}` 经过 {MAX_ATTEMPTS} 次尝试仍失败。")

        task.ended_at = time.time()

        if timed_out and task.status == STATUS_TIMEOUT:
            continue
        if success:
            task.status = STATUS_SUCCESS
            log("SUCCESS", f"任务 `{task.name}` 执行成功（耗时 {task.duration:.2f}s，"
                           f"尝试 {task.attempts} 次）。")
        else:
            # 全部尝试失败 → 跳过
            task.status = STATUS_SKIPPED
            log("SKIPPED", f"任务 `{task.name}` 达到最大重试次数，标记为 SKIPPED。")

    total_duration = time.time() - start_time

    report = {
        "timeout": timed_out,
        "total_duration": round(total_duration, 3),
        "tasks": [
            {
                "name": t.name,
                "status": t.status,
                "attempts": t.attempts,
                "duration": t.duration,
                "started_at": round(t.started_at, 3) if t.started_at is not None else None,
                "ended_at": round(t.ended_at, 3) if t.ended_at is not None else None,
            }
            for t in tasks
        ],
    }
    return report


# --------------------------------------------------------------------------- #
# 报告写入
# --------------------------------------------------------------------------- #

def write_report(report: Dict[str, Any], path: str) -> None:
    ext = os.path.splitext(path)[1].lower()
    try:
        if ext == ".json":
            with open(path, "w", encoding="utf-8") as f:
                json.dump(report, f, ensure_ascii=False, indent=2)
        elif ext in (".yaml", ".yml"):
            if yaml is None:
                die("未安装 PyYAML，无法写入 YAML 报告。")
            with open(path, "w", encoding="utf-8") as f:
                yaml.safe_dump(report, f, allow_unicode=True, sort_keys=False)
        else:
            die(f"不支持的报告扩展名: {ext}（仅支持 .json/.yaml/.yml）")
    except OSError as e:
        die(f"无法写入报告文件: {path} ({e})")
    log("INFO", f"报告已写入: {path}")


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="scheduler.py",
        description="命令行任务调度模拟器：按依赖顺序执行任务，支持重试、超时与报告生成。",
    )
    p.add_argument("--config", required=True,
                   help="任务配置文件路径（.yaml / .yml / .json）")
    p.add_argument("--timeout", type=float, default=None,
                   help="全局超时时间（秒），覆盖配置文件中的 timeout 字段")
    p.add_argument("--report", default="report.json",
                   help="报告输出路径，默认 report.json（支持 .json/.yaml/.yml）")
    p.add_argument("--seed", type=int, default=None,
                   help="随机数种子，用于复现结果")
    p.add_argument("--no-color", action="store_true",
                   help="禁用彩色输出")
    return p


def main(argv: Optional[List[str]] = None) -> int:
    global _USE_COLOR

    parser = build_parser()
    args = parser.parse_args(argv)

    # 彩色输出：仅在 TTY 且未显式禁用时启用
    _USE_COLOR = sys.stdout.isatty() and not args.no_color
    if _USE_COLOR:
        _enable_vt_processing()

    # 随机种子
    rng = random.Random(args.seed)
    if args.seed is not None:
        log("INFO", f"使用随机种子: {args.seed}")

    # 加载配置
    data = load_config_safe(args.config)
    tasks = parse_tasks(data)
    ordered = topo_sort(tasks)

    # 超时：CLI 优先，其次配置文件
    timeout = args.timeout
    if timeout is None:
        cfg_timeout = data.get("timeout")
        if cfg_timeout is not None:
            if not isinstance(cfg_timeout, (int, float)) or isinstance(cfg_timeout, bool) or cfg_timeout <= 0:
                die("配置中的 `timeout` 必须是正数。")
            timeout = float(cfg_timeout)

    log("INFO", f"共加载 {len(ordered)} 个任务，"
                f"{'超时 ' + f'{timeout:.2f}s' if timeout else '无超时限制'}。")

    # 执行
    report = run_scheduler(ordered, timeout, rng)

    # 写报告
    write_report(report, args.report)

    # 汇总
    succ = sum(1 for t in report["tasks"] if t["status"] == STATUS_SUCCESS)
    skip = sum(1 for t in report["tasks"] if t["status"] == STATUS_SKIPPED)
    tout = sum(1 for t in report["tasks"] if t["status"] == STATUS_TIMEOUT)
    log("INFO", f"执行完毕：成功 {succ}，跳过 {skip}，超时 {tout}，"
                f"总耗时 {report['total_duration']:.3f}s，"
                f"{'超时' if report['timeout'] else '未超时'}。")

    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except SystemExit:
        raise
    except KeyboardInterrupt:
        print(f"\n{_colorize('[ERROR]', _COLOR_RED)} 用户中断。", file=sys.stderr)
        sys.exit(130)
    except Exception as e:  # 兜底：禁止栈回溯
        print(f"{_colorize('[ERROR]', _COLOR_RED)} 未预期的错误: {e}", file=sys.stderr)
        sys.exit(1)
