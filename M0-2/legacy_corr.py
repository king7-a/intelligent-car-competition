import argparse
import csv
import math
import os
import sys

import yaml

def load_config(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)

    if cfg is None:
        raise ValueError("配置文件为空或格式不正确")

    csv_path = cfg["input_csv"]
    col_x = cfg["columns"]["x"]
    col_y = cfg["columns"]["y"]
    verbose = cfg.get("task", {}).get("verbose", False)

    # 相对路径以配置文件所在目录为基准
    if not os.path.isabs(csv_path):
        base_dir = os.path.dirname(os.path.abspath(config_path))
        csv_path = os.path.join(base_dir, csv_path)

    return csv_path, col_x, col_y, verbose

def load_csv_data(csv_path, col_x, col_y):
    if not os.path.exists(csv_path):
        raise FileNotFoundError(f"数据文件不存在: {csv_path}")

    xs, ys = [], []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames is None:
            raise ValueError("CSV 文件为空或没有表头")

        if col_x not in reader.fieldnames:
            raise KeyError(f"CSV 中找不到列 '{col_x}'，可用列: {reader.fieldnames}")
        if col_y not in reader.fieldnames:
            raise KeyError(f"CSV 中找不到列 '{col_y}'，可用列: {reader.fieldnames}")

        for row in reader:
            xs.append(float(row[col_x]))
            ys.append(float(row[col_y]))

    if len(xs) == 0:
        raise ValueError("CSV 数据行为空（只有表头，没有数据）")
    if len(xs) < 2:
        raise ValueError("数据不足两行，无法计算相关系数")

    return xs, ys

def pearson_correlation(xs, ys):
    n = len(xs)
    if n != len(ys):
        raise ValueError(f"两列长度不一致: x={n}, y={len(ys)}")

    mean_x = sum(xs) / n
    mean_y = sum(ys) / n

    sum_dx2 = 0.0
    sum_dy2 = 0.0
    sum_dxdy = 0.0

    for i in range(n):
        a = xs[i] - mean_x
        b = ys[i] - mean_y
        sum_dx2 += a * a
        sum_dy2 += b * b
        sum_dxdy += a * b

    denom = math.sqrt(sum_dx2 * sum_dy2)
    if denom == 0.0:
        raise ZeroDivisionError("某列方差为 0（取值恒定），相关系数无定义")

    r = sum_dxdy / denom
    return r

def main():
    parser = argparse.ArgumentParser(description="计算两列数据的 Pearson 相关系数")
    parser.add_argument(
        "--config", default="config.yaml", help="YAML 配置文件路径"
    )
    args = parser.parse_args()

    try:
        csv_path, col_x, col_y, verbose = load_config(args.config)
        xs, ys = load_csv_data(csv_path, col_x, col_y)
        r = pearson_correlation(xs, ys)

        n = len(xs)
        mean_x = sum(xs) / n
        mean_y = sum(ys) / n

        if verbose:
            print(f"n = {n}")
            print(f"mean_x = {mean_x}")
            print(f"mean_y = {mean_y}")
        print(f"r = {r}")
        return 0

    except FileNotFoundError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1
    except KeyError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1
    except ValueError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1
    except ZeroDivisionError as e:
        print(f"[错误] {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"[错误] 意外异常: {e}", file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
