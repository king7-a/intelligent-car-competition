# M0-1 从零搭建开发环境

## 一、环境方案说明

本次开发环境采用 WSL2 搭载 Ubuntu 22.04 LTS 的方案实现，无需重装物理机双系统，可同时兼顾 Windows 日常使用与 Linux 开发需求，配合 VS Code 的 WSL 远程开发插件，实现可视化编码与终端操作一体化。

最终搭建完成的环境包含：WSL2 Ubuntu 22.04.5 LTS 系统、ROS2 Humble 机器人开发框架、Python 3.10 + venv 虚拟环境、GCC/G++ 编译工具链、VS Code 开发工具、Git 版本控制工具。

## 二、安装配置过程

### 1. WSL2 与 Ubuntu 22.04 安装

首先在 Windows 的「启用或关闭 Windows 功能」面板中，勾选「适用于 Linux 的 Windows 子系统」和「虚拟机平台」两个选项，完成后重启电脑。重启后以管理员身份打开 PowerShell，执行 `wsl --set-default-version 2` 将默认 WSL 版本设置为 2。之后打开微软应用商店，搜索 Ubuntu 22.04 LTS 并安装，首次启动时设置好 Linux 系统的用户名与密码。

系统安装完成后，先备份 `/etc/apt/sources.list` 文件，将软件源替换为清华镜像源，然后依次执行 `sudo apt update` 和 `sudo apt upgrade` 命令更新系统软件包。

### 2. ROS2 Humble 安装

先配置 ROS2 的官方软件源与 GPG 密钥，完成后执行 `sudo apt install ros-humble-desktop` 安装桌面完整版 ROS2。安装完成后将 `source /opt/ros/humble/setup.bash` 写入 `~/.bashrc` 文件，实现开机自动配置 ROS2 环境变量。最后安装 `python3-colcon-common-extensions` 和 `python3-rosdep` 等辅助工具，并执行 `rosdep init` 与 `rosdep update` 完成依赖初始化。

### 3. Python 虚拟环境配置

先执行 `sudo apt install python3-venv python3-pip` 安装 venv 模块与 pip 包管理工具。在项目根目录下执行 `python3 -m venv .venv` 创建虚拟环境，通过 `source .venv/bin/activate` 命令激活环境，激活成功后终端提示符前会出现 `(.venv)` 标识。之后升级 pip 并配置国内镜像源，后续项目依赖均通过 `requirements.txt` 文件管理，使用 `pip install -r requirements.txt` 命令统一安装。

### 4. C/C++ 开发环境

执行 `sudo apt install build-essential cmake gdb` 安装编译工具链、CMake 构建工具与 GDB 调试工具，安装完成后可通过 `gcc --version`、`g++ --version` 命令验证版本。

### 5. VS Code 与插件配置

在 Windows 端安装 VS Code 编辑器，然后安装 WSL 扩展插件，用于远程连接 WSL 内的 Linux 环境。开发时在 WSL 终端进入项目目录，执行 `code .` 命令即可一键拉起 VS Code 并自动加载当前项目，左下角会显示 WSL: Ubuntu-22.04 标识。同时在 WSL 环境下安装 Python、C/C++、ROS、GitLens、YAML 等开发插件。

### 6. Git 配置与仓库初始化

执行 `sudo apt install git` 安装版本控制工具，安装完成后通过 `git config --global` 命令配置全局用户名与邮箱，与 GitHub 账号保持一致。在项目根目录执行 `git init` 命令初始化本地仓库，之后关联 GitHub 远程仓库，并将默认分支重命名为 main。

## 三、本机踩坑实录

### 坑 1：VS Code 打开项目识别不到 Git 仓库

- **现象**：VS Code 左侧源代码管理面板提示未检测到 Git 仓库，但在 WSL 终端中执行 Git 命令一切正常
- **原因**：通过 Windows 本地磁盘路径打开文件夹时，VS Code 调用的是 Windows 系统的 Git 程序，而我们的 Git 工具与代码仓库都部署在 WSL 的 Linux 环境中，两边环境不互通
- **解决过程**：先在 WSL 终端中进入项目根目录，再执行 `code .` 命令启动 VS Code，此时左下角会显示 WSL: Ubuntu-22.04，确认终端路径为 `/home/用户名/项目名`，而非 `/mnt/c/` 开头的 Windows 路径，即可正常识别 Git 仓库。

### 坑 2：首次执行 git commit 报错缺少身份信息

- **现象**：执行 git commit 命令时报错 Author identity unknown，无法完成提交
- **原因**：新安装的 Git 未配置全局用户名与邮箱，每次提交需要绑定提交者身份信息
- **解决过程**：执行两条 `git config --global` 命令分别配置用户名和注册邮箱，配置后永久生效。可通过 `git config --global --list` 命令查看所有全局配置，确认信息无误。

### 坑 3：git push 推送 GitHub 时连接失败

- **现象**：执行 git push 时报错 Failed to connect to [github.com](https://github.com) port 443: Connection refused，无法推送代码到远程仓库
- **原因**：国内网络访问 GitHub 不稳定，部分校园网或运营商会限制 443 端口连接
- **解决过程**：先重试 2-3 次，多数临时网络波动可自行恢复；如果仍失败则切换手机热点网络重试；如果使用了代理工具，需要为 Git 单独配置代理参数。

### 坑 4：WSL 终端出现乱码字符

- **现象**：终端提示符、命令输出出现大量乱码转义字符，显示异常
- **原因**：系统 locale 编码配置不匹配
- **解决过程**：执行 `sudo dpkg-reconfigure locales` 命令进入配置界面，选择 `en_US.UTF-8` 并设为系统默认，重启终端后显示恢复正常。

### 坑 5：虚拟环境激活报错

- **现象**：执行 `source .venv/bin/activate` 命令时提示 No such file or directory，无法激活虚拟环境
- **原因**：未在项目根目录下执行命令，或是未安装 python3-venv 包导致虚拟环境创建失败
- **解决过程**：先确认当前处于项目根目录，再执行 `sudo apt install python3-venv` 重新安装依赖包，之后删除旧的 `.venv` 文件夹，重新执行 `python3 -m venv .venv` 创建虚拟环境。

## 四、环境验证方法

搭建完成后可通过对应命令验证各组件是否正常：

- Ubuntu 系统：执行 `lsb_release -a`，确认版本号为 22.04
- ROS2：执行 `ros2 doctor`，大部分检查项显示通过即为正常
- Python：执行 `python3 --version`，确认版本为 3.10.x
- 虚拟环境：激活后终端前缀出现 `(.venv)` 标识
- GCC 编译链：执行 `gcc --version`，确认版本为 11.x
- Git：执行 `git --version`，正常输出版本号
- VS Code 远程连接：左下角显示 WSL: Ubuntu-22.04，可正常编辑 Linux 文件
然后在对应文件夹打开