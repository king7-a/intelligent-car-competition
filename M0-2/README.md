M0-2 环境配置与 Git 操作指南

一、Python 虚拟环境配置

1. 安装系统依赖
sudo apt update
sudo apt install python3.10-venv -y
2. 创建虚拟环境
cd ~/smartcar_ws/M0-2
rm -rf venv
python3.10 -m venv venv
3. 激活虚拟环境
. venv/bin/activate
4. 安装依赖包
pip install pyyaml numpy pytest
5. 验证环境
which python
python --version
pip list

二、文件导入 Git 仓库操作

1. 物理复制文件到项目目录
方法 1：拖拽复制（推荐）
VS Code 连接 WSL 打开 M0-2 文件夹后，直接将 Windows 本地的文件拖拽到左侧资源管理器空白处，选择复制即可。

方法 2：终端命令复制
复制单个文件
cp 源文件路径～/smartcar_ws/M0-2/

复制整个文件夹
cp -r 源文件夹路径～/smartcar_ws/M0-2/

2. 文件正式提交入库
git add .
git commit -m "添加项目文件"
3. 关联并推送到 GitHub 远程仓库

# 关联远程仓库（替换为你自己的 GitHub 仓库地址）

git remote add origin [https://github.com/](https://github.com/)你的用户名 / 仓库名.git
git branch -M master

# 首次推送到远程仓库

git push -u origin master

三、常见问题

1. 提示 source: not found：使用. venv/bin/activate 代替 source 命令
2. 提示 ensurepip is not available：执行第一步安装系统依赖即可
3. 运行代码找不到包：重新执行第三步激活虚拟环境
4. Git 看不到子文件夹改动：删除子文件夹内的.git 目录，命令：rm -rf 子文件夹路径 /.git

原始文件`legacy_corr.py` 一共 50 行，全部是裸代码，没有函数封装，没有异常处理，没有`if __name__` 保护，公式还写错了。下面按修改步骤说明。

第一步，补 import。原来只有三行 import，分别是 yaml、csv、math。现在加上了 argparse、os、sys 三个模块。argparse 用于接收命令行参数`--config` ，os 用于检查文件是否存在和解析相对路径，sys 用于向 stderr 输出错误信息和控制退出码。

第二步，删掉第 5 行的硬编码路径。原来写死了`CONFIG_PATH = "config.yaml"` ，无法从命令行指定其他配置文件。现在改为在 main 函数里用 argparse 接收`--config` 参数，默认值仍然是`config.yaml` ，但用户可以自行指定。

第三步，把第 7 到 12 行的配置读取逻辑封装成`load_config` 函数。原来的代码直接`open(CONFIG_PATH)` 读 yaml，如果文件不存在直接崩溃，没有任何提示。现在函数里加了`if cfg is None` 的检查，防止配置文件为空时后续取键报 TypeError。同时增加了读取 verbose 配置项的逻辑，用于控制是否打印中间量。另外加了相对路径解析：如果 yaml 里写的 CSV 路径是相对路径，就以配置文件所在目录为基准去查找，而不是以当前工作目录为基准。函数最后 return 四个值：csv_path、col_x、col_y、verbose。

第四步，把第 14 到 21 行的 CSV 读取逻辑封装成`load_csv_data` 函数。原来的代码直接`open(csv_path)` 读 CSV，存在多个问题：文件不存在时直接 FileNotFoundError 崩溃；空 CSV 没有表头时`reader.fieldnames` 是 None 不报错但后续`float(None)` 崩溃；列名不对时直接 KeyError 崩溃；数据不足两行时 n 等于 0 或 1，后续除零崩溃。现在函数里依次加了文件存在检查、空文件检查、列名匹配检查、数据量检查，哪个环节出问题就 raise 对应的异常并附带可读的错误信息。函数最后 return xs 和 ys 两个列表。

第五步，把第 23 到 45 行的计算逻辑封装成`pearson_correlation` 函数，同时修复公式。这是最关键的一步。原来的代码有两个问题。第一个问题是公式写错：第 44 行`denom = dx * dy` ，少了一个`math.sqrt()` 。Pearson 相关系数的分母应该是 sqrt(dx 乘以 dy)，而不是 dx 乘以 dy。这个错误导致结果差了好几个数量级，原始数据算出来是 0.000156，正确值应该是 0.5635。第二个问题是没有任何零方差保护：如果某一列取值恒定（比如全是 1.0），那么 dx 或 dy 就是 0，denom 就是 0，`prod / 0` 直接除零崩溃。现在函数里把分母改成了`math.sqrt(sum_dx2 * sum_dy2)` ，并且加了`if denom == 0.0` 的检查，遇到零方差时 raise ZeroDivisionError 并给出提示。另外还加了两列长度不一致的检查。函数最后 return r。

第六步，把第 47 到 50 行的打印逻辑封装成`main` 函数，加上异常处理和`if __name__` 保护。原来的代码直接裸 print，任何异常都会抛出 Python 的 Traceback 给用户，非常不友好。现在 main 函数里把整个流程包在 try/except 里，依次捕获 FileNotFoundError、KeyError、ValueError、ZeroDivisionError 和兜底的 Exception，每类异常都打印`[错误]` 加上具体信息到 stderr，并返回非零退出码。正常情况返回 0。最后加上`if __name__ == "__main__": sys.exit(main())` ，这样脚本被 import 时不会执行主逻辑。

以上就是从原始文件到最终文件的完整修改过程。核心修复是第五步的公式 bug：第 44 行`denom = dx * dy` 改成`denom = math.sqrt(sum_dx2 * sum_dy2)` ，补上了缺失的平方根。
