# TaskScheduler

命令行下的**任务调度模拟器**。把"任务状态管理"和"时间监控"抽象成代码：
按依赖顺序（拓扑排序）执行一组任务，模拟真实耗时与随机成败，
支持失败重试、依赖失败传播、全局超时、彩色日志与 JSON 报告。

不依赖任何 ROS 或 GUI，全在终端运行。

---

## 环境准备

必须使用虚拟环境：

```bash
# 创建虚拟环境
python -m venv .venv

# 激活虚拟环境
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# Linux / macOS:
source .venv/bin/activate

# 安装依赖
pip install -r requirements.txt
```

唯一的第三方依赖是 `PyYAML`（用于解析 `.yaml` 配置）。

---

## 参数说明

```bash
python scheduler.py --config <path> [--timeout <float>] [--report <path>] [--seed <int>] [--no-color]
```

| 参数 | 必填 | 默认值 | 说明 |
| :-- | :--: | :-- | :-- |
| `--config <path>` | **是** | — | 任务配置文件路径，支持 `.yaml` / `.yml` / `.json` |
| `--timeout <float>` | 否 | 配置文件中的 `timeout` | 全局超时时间（秒），**覆盖**配置文件中的 `timeout` 字段 |
| `--report <path>` | 否 | `report.json` | 报告输出路径，支持 `.json` / `.yaml` / `.yml` |
| `--seed <int>` | 否 | 随机 | 随机数种子，用于**复现**同一结果 |
| `--no-color` | 否 | 关闭 | 禁用彩色输出（非 TTY 环境会自动降级） |

> 若配置文件中没有 `timeout` 且未传 `--timeout`，则不设超时限制。

---

## 配置文件格式

```yaml
timeout: 15          # 可选，全局超时（秒）

tasks:
  - name: "Navigate"         # 任务名（唯一）
    duration: 2.5            # 预期耗时（秒），程序会 sleep(duration)
    success_rate: 0.8        # 模拟成功率 0~1
    dependencies: ["Init"]   # 依赖的前置任务列表
```

- `name`：任务名，必须唯一。
- `duration`：非负数字，模拟执行耗时。
- `success_rate`：`0.0 ~ 1.0`，每次尝试的成功率。
- `dependencies`：前置任务名列表，必须全部 `SUCCESS` 才会执行本任务。

本目录提供 `tasks_demo.yaml` 与 `tasks_demo.json`（内容等价）作为示例。

---

## 调度规则

1. **拓扑排序**：按依赖顺序执行，正确处理分叉 / 汇合；检测到**依赖环**时报错退出。
2. **成败判定**：每个任务根据 `success_rate` 随机判定成功或失败。
3. **重试**：失败后最多重试 2 次（共 3 次尝试）；仍失败则标记为 `SKIPPED`。
4. **依赖传播**：若某任务被 `SKIPPED` / `TIMEOUT`，其所有下游任务均标记为 `SKIPPED`。
5. **超时**：执行前与每次 `sleep` 后各检查一次；超出 `timeout` 立即终止，未执行的任务标记为 `TIMEOUT`。

---

## 运行示例

### 示例 1：基本运行（使用示例配置 + 固定种子）

```bash
python scheduler.py --config tasks_demo.yaml --timeout 15 --report report.json --seed 42
```

输出（节选）：

```
[INFO] 使用随机种子: 42
[INFO] 共加载 7 个任务，超时 15.00s。
[SUCCESS] 任务 `Init` 执行成功（耗时 0.50s，尝试 1 次）。
[SUCCESS] 任务 `Navigate` 执行成功（耗时 2.50s，尝试 1 次）。
...
[SKIPPED] 任务 `AvoidObstacle` 达到最大重试次数，标记为 SKIPPED。
[SKIPPED] 任务 `Place` 因依赖未成功而跳过（AvoidObstacle(SKIPPED)）。
[INFO] 执行完毕：成功 4，跳过 3，超时 0，总耗时 11.508s，未超时。
```

生成的 `report.json` 结构：

```json
{
  "timeout": false,
  "total_duration": 11.508,
  "tasks": [
    {
      "name": "Init",
      "status": "SUCCESS",
      "attempts": 1,
      "duration": 0.5,
      "started_at": 1792148370.591,
      "ended_at": 1792148371.092
    }
  ]
}
```

### 示例 2：触发超时（超时时间小于任务总耗时）

```bash
python scheduler.py --config tasks_demo.json --timeout 2 --report timeout_report.json --seed 1
```

输出（节选）：

```
[SUCCESS] 任务 `Init` 执行成功（耗时 0.50s，尝试 1 次）。
[TIMEOUT] 任务 `Navigate` 执行耗时超出全局超时（2.00s）。
[INFO] 执行完毕：成功 1，跳过 0，超时 6，总耗时 3.001s，超时。
```

此时 `report.json` 中 `timeout` 为 `true`，未执行的任务状态为 `TIMEOUT`。

### 示例 3：不设超时 + 更换种子观察不同结果

```bash
# 不设超时，使用 JSON 配置
python scheduler.py --config tasks_demo.json --seed 100

# 使用 YAML 报告输出
python scheduler.py --config tasks_demo.yaml --report report.yaml --seed 7
```

不同 `--seed` 会得到不同的随机成败序列；相同 `--seed` 结果可复现。

---

## 报告字段说明

| 字段 | 类型 | 说明 |
| :-- | :-- | :-- |
| `timeout` | bool | 是否发生全局超时 |
| `total_duration` | float | 程序总耗时（秒） |
| `tasks[].name` | string | 任务名 |
| `tasks[].status` | string | `SUCCESS` / `FAILED` / `SKIPPED` / `TIMEOUT` |
| `tasks[].attempts` | int | 尝试次数，不超过 3 |
| `tasks[].duration` | float | 任务配置的预期耗时（秒） |
| `tasks[].started_at` | float/null | 开始执行的时间戳（未执行为 null） |
| `tasks[].ended_at` | float/null | 结束执行的时间戳（未执行为 null） |

---

## 异常处理

以下情况会给出可读错误提示并以**非 0 退出**，不抛出栈回溯：

- 配置文件不存在
- YAML / JSON 语法错误
- `tasks` 为空或不是列表
- 任务名重复 / 缺失
- `duration` 非非负数字
- `success_rate` 超出 `0~1`
- 依赖了不存在的任务
- 存在依赖环
- 报告文件无法写入

---

## 文件清单

| 路径 | 内容 |
| :-- | :-- |
| `scheduler.py` | 主程序 |
| `requirements.txt` | 依赖清单 |
| `tasks_demo.yaml` | 示例任务配置（YAML） |
| `tasks_demo.json` | 示例任务配置（JSON，与 YAML 等价） |
| `report.json` | 一次运行产生的报告样例 |
| `README.md` | 本文档 |
