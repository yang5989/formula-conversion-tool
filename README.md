# Formula Conversion Tool

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.12-blue.svg)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/Platform-Windows-lightgrey.svg)]()

Screenshot a formula → get LaTeX → paste into Word as a **real, editable equation**.

截图公式 → 识别为 LaTeX → 粘贴进 Word 变成**可编辑的公式对象**。

---

## Table of Contents / 目录

- [Why / 为什么做这个](#why--为什么做这个)
- [Features / 功能](#features--功能)
- [Requirements / 环境要求](#requirements--环境要求)
- [Installation / 安装](#installation--安装)
- [Usage / 使用](#usage--使用)
- [How it works / 工作原理](#how-it-works--工作原理)
- [Known limitations / 已知限制](#known-limitations--已知限制)
- [Project structure / 项目结构](#project-structure--项目结构)
- [License / 许可](#license--许可)

---

## Why / 为什么做这个

Writing formulas into Word by hand is slow and error-prone — especially nested
fractions, matrices, and summation symbols. This tool reads the formula from a
screenshot and gives you a LaTeX string, then copies it to the clipboard in a
format Word natively understands: **a real equation object**, not formatted text.

手工往 Word 里敲公式又慢又容易错，尤其是多层分数、矩阵、求和符号。这个工具
从截图识别出 LaTeX，再以 Word 原生能认的格式放进剪贴板——粘进去是**真正的
公式对象**，不是一堆格式化的文字。

**Accuracy / 准确率**：86% usable rate on 14 standard test formulas (see
[docs/benchmark.md](docs/benchmark.md)). Complex matrices and tensor equations
may still need manual correction.

---

## Features / 功能

| Feature | 说明 |
|---|---|
| Screenshot OCR | Global hotkey `Ctrl+Alt+Q` → select region → recognize |
| 截图识别 | 全局热键 `Ctrl+Alt+Q` → 框选区域 → 自动识别 |
| Word equation output | Paste into Word → editable equation object |
| Word 公式输出 | 粘进 Word → 可编辑公式对象 |
| Multiple output formats | Word equation / LaTeX / MathML / plain text |
| 多种输出格式 | Word 公式 / LaTeX / MathML / 纯文本 |
| Tray resident | Close to tray, hotkey always available |
| 托盘常驻 | 关窗到托盘，热键随时可用 |
| History | Last 200 formulas, deduplicated, one-click reuse |
| 历史记录 | 最近 200 条，自动去重，一键复用 |
| Configurable tips | 7 independent notification switches |
| 提示开关 | 7 个提示各自独立开关 |
| Fully offline | No network, no API key, no quota |
| 完全离线 | 不联网、不需 API key、无额度限制 |

---

## Requirements / 环境要求

> ⚠️ **Python 3.12 is required.** Python 3.14+ cannot install `onnxruntime`,
> which `pix2text` depends on.
>
> **必须使用 Python 3.12。** Python 3.14+ 装不了 `onnxruntime`，而
> `pix2text` 依赖它。

| Component | Version | Note |
|---|---|---|
| Python | **3.12** | 3.14+ will fail |
| OS | Windows 10/11 | Word formula output requires Word 2016+ |
| Word | 2016 or later | For equation object paste |
| Disk | ~2 GB | Model weights + dependencies |

---

## Installation / 安装

### 方式一：一键安装（推荐）

**Windows 用户下载后直接双击 `install.bat`。**

脚本会自动完成：

1. 查找 Python 3.12（`py -3.12` → `python` → `python3` → 常见安装路径）
2. 找不到就用 [uv](https://github.com/astral-sh/uv) 自动下载（不影响系统已有 Python）
3. 创建虚拟环境 `.venv/`
4. 安装依赖（约 2 GB，5-15 分钟）
5. 验证版本（Python 3.12 / rapidocr 3.9.2）
6. 生成两个启动器：
   - `启动.bat` —— 正常运行（无控制台窗口）
   - `启动(调试模式).bat` —— 出错时能看到完整报错

装完后双击 `启动.bat` 即可使用。

> **装不上怎么办**：双击 `启动(调试模式).bat`，把窗口里的报错截图发到 Issues。
>
> **If setup fails**: run `启动(调试模式).bat` and post the error output in Issues.

---

### 方式二：手动安装

适合想自己控制环境、或用 macOS / Linux 的用户。

#### 1. Get Python 3.12 / 获取 Python 3.12

```bash
# 用 uv（推荐）
pip install uv
uv python install 3.12
```

或从 [python.org](https://www.python.org/downloads/) 下载。

#### 2. Create virtual environment / 创建虚拟环境

```bash
cd formula-conversion-tool
uv venv --python 3.12 .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate # macOS / Linux
```

#### 3. Install dependencies / 安装依赖

```bash
pip install -r requirements.txt
```

> **Important**: `rapidocr` must stay at version `3.9.2`.
> Version 3.10+ removed the `resolve_model_key` function, which breaks `cnstd`.
>
> **重要**：`rapidocr` 必须锁定在 `3.9.2`。3.10+ 移除了 `resolve_model_key`
> 函数，会导致 `cnstd` 崩溃。

大陆网络下载慢可换镜像：

```bash
pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple
```

#### 4. First run / 首次运行

```bash
python run.py
```

The first launch downloads model weights (~400 MB) from Hugging Face and takes
1-3 minutes. Subsequent launches take about 12 seconds.

首次启动会从 Hugging Face 下载模型权重（约 400 MB），耗时 1-3 分钟。
之后启动约 12 秒。

---

### 为什么没有 exe / Why no exe?

试过 PyInstaller 打包，结果 **1.3 GB** 且运行时报错
`RuntimeError: operator torchvision::nms does not exist`
（torchvision 的原生扩展没被正确打包）。体积和维护成本都不划算，
所以改用脚本安装方案。

Tried PyInstaller: the build was 1.3 GB and failed at runtime with
`RuntimeError: operator torchvision::nms does not exist`. Not worth the size
and maintenance cost, so this project ships an installer script instead.

---

## Usage / 使用

### Quick start / 快速开始

1. Launch: `python run.py`
2. Press `Ctrl+Alt+Q` anywhere (or click the 截图 button)
3. Drag to select the formula region
4. Wait 1-3 seconds
5. Click **复制公式** (Copy formula)
6. Paste into Word with `Ctrl+V` → it becomes an editable equation

### 界面说明

```
┌──────────────────────────────────────┐
│  [截图] [打开图片] [粘贴] [历史] [设置] │
├──────────────────────────────────────┤
│                                      │
│         图片预览区                     │
│    （支持拖入 / Ctrl+V / 框选）         │
│                                      │
├──────────────────────────────────────┤
│  识别结果（可编辑）                     │
│  \frac{-b\pm\sqrt{b^2-4ac}}{2a}      │
├──────────────────────────────────────┤
│  输出格式: [Word 公式 ▾] [复制公式]     │
└──────────────────────────────────────┘
```

### Output formats / 输出格式

| Mode | Paste into Word gives | Use case |
|---|---|---|
| **Word 公式** | Editable equation object | Writing reports |
| **LaTeX 源码** | Plain text `\frac{...}` | Papers, Markdown, GitHub |
| **MathML** | XML markup | Web pages, publishing systems |
| **纯文本近似** | `frac-b ± √b^2-4ac2a` | Chat, notepad |

### Keyboard shortcuts / 快捷键

| Key | Action |
|---|---|
| `Ctrl+Alt+Q` | Global screenshot (works in any app) |
| `Ctrl+V` | Paste image from clipboard |
| `Ctrl+O` | Open image file |
| `Ctrl+Shift+C` | Copy with current format |
| `Ctrl+H` | History |

---

## How it works / 工作原理

```
Screenshot
   ↓
P2T (pix2text) — image → LaTeX
   ↓
Post-processing (postprocess.py)
   · fix spaced commands:  \operatorname*{l i m} → \lim
   · fix redundant spacing
   ↓
Matrix repair (matrix_fix.py)
   · wrong column count: {c c} → 4 columns
   · cells joined by \, → split with &
   · array → vmatrix/pmatrix/bmatrix
   ↓
LaTeX → MathML (latex2mathml)
   ↓
MathML → OMML (Word's MML2OMML.XSL)
   ↓
OMML delimiter repair (omml_fix.py)
   · character delimiters → <m:d> objects
   ↓
Clipboard (HTML Format with CF_HTML offsets)
   ↓
Paste into Word → editable equation
```

### Why so many steps?

Word's equation format is OMML (Office Math Markup Language). The official
conversion path is LaTeX → MathML → OMML. Each stage loses or mangles something,
so each stage needs repair:

1. `latex2mathml` writes matrix delimiters as plain characters, not delimiters
2. `MML2OMML.XSL` merges adjacent runs, swallowing `(` into `A=(`
3. OMML needs `<m:d>` wrapper for delimiters to stretch to content height
4. Clipboard HTML needs specific quoting or Word renders a broken placeholder

### 为什么这么多层

Word 的公式格式是 OMML，官方转换路径是 LaTeX → MathML → OMML。每一层都会
丢东西或弄错东西：

1. `latex2mathml` 把矩阵定界符当普通字符写
2. `MML2OMML.XSL` 会合并相邻 run，把 `(` 吞进 `A=(`
3. OMML 需要 `<m:d>` 包裹，定界符才会伸展到内容高度
4. 剪贴板 HTML 的引号写法不对，Word 会渲染成虚线占位框

---

## Known limitations / 已知限制

| Limitation | 说明 | Status |
|---|---|---|
| Matrix delimiter height | 矩阵括号高度偶尔不足 | 待优化 |
| Piecewise functions | `\begin{cases}` 识别不稳 | 已知 |
| Bold letters | `\mathbf{J}` 可能认成 `\eta` | 已知 |
| Handwriting | 工整手写可用，潦草则不准 | 部分支持 |
| Multi-line formulas | 长推导需手动切分 | 不计划支持 |
| Word only | 目前只输出 Word 公式，WPS 未测试 | 待测试 |

See [docs/TODO.md](docs/TODO.md) for details.

---

## Project structure / 项目结构

```
formula-conversion-tool/
├── src/
│   ├── engine.py           Recognition engine wrapper
│   ├── postprocess.py      LaTeX post-processing
│   ├── matrix_fix.py       Matrix structure repair
│   ├── omml_fix.py         OMML delimiter repair
│   ├── export_word.py      Word formula clipboard output
│   ├── capture.py          Screenshot & region selection
│   ├── history.py          History storage
│   ├── settings.py         Settings persistence
│   ├── output.py           Output mode definitions
│   ├── notify.py           Notification dispatcher
│   ├── main.py             Entry point
│   └── ui/
│       ├── window.py       Main window
│       ├── splash.py       Splash screen
│       ├── tray.py         System tray
│       ├── hotkey.py       Win32 global hotkey
│       ├── winfocus.py     Force foreground window
│       ├── settings_dialog.py  Settings panel
│       └── history_panel.py    History panel
├── docs/
│   ├── benchmark.md        Engine selection experiment data
│   └── TODO.md             Known issues
├── requirements.txt
├── run.py
└── LICENSE
```

---

## License / 许可

[MIT](LICENSE) © 2026

---

## Acknowledgements / 致谢

- [pix2text](https://github.com/breezedeus/Pix2Text) — formula recognition model
- [latex2mathml](https://github.com/roniemartinez/latex2mathml) — LaTeX to MathML
- [PySide6](https://www.qt.io/qt-for-python) — GUI framework
- The MML2OMML.XSL converter ships with Microsoft Office
