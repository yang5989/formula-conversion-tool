# 引擎选型实验数据

**测试日期**：2026-11-22
**测试机**：Windows / RTX 5060 Laptop / 31.4 GB RAM
**测试集**：14 张标准公式图（matplotlib 渲染，200 DPI）

---

## 一、pix2tex 0.1.4（Python 3.15）

| 指标 | 结果 |
|---|---|
| 完全正确 | 1/14（7%） |
| 语义等价 | 2/14 |
| **可用率** | **3/14 = 21%** |
| 平均耗时 | 0.45 s/张 |

### 典型错误

| 公式 | 期望 | 实际输出 | 错误类型 |
|---|---|---|---|
| 二次公式 | `\frac{-b\pm\sqrt{b^2-4ac}}{2a}` | `\frac{-b\pm\sqrt{b^2-4\phi C}}{2\partial}` | c→φC，a→∂ |
| 高斯积分 | `e^{-x^2}dx=\frac{\sqrt{\pi}}{2}` | `\Theta^{-2^2}Q\lambda\not L\longrightarrow...` | 结构崩坏 |
| 级数求和 | `n^2` | `\eta^2`（六处） | 近形字混淆 |
| 正态分布 | `e^{-\frac{...}{2\sigma^2}}` | `\Theta^{-\frac{...}{2\sigma^2}}` | e→Θ |
| 行列式 | `\det(A)` | `\operatorname{Qet}(A)` | d→Q |

**失败原因**：模型权重训练于 2023 年前后，与 Python 3.15 + transformers 5.24 不兼容。
运行时警告 `torch.jit.script is not supported in Python 3.14+` 是直接证据 ——
模型的部分模块在 3.15 上未正常工作。

---

## 二、P2T (pix2text 1.1.7) — Python 3.12

| 指标 | 结果 |
|---|---|
| 完全一致 | 6/14（43%） |
| 语义等价 | 6/14（43%） |
| 实质错误 | 2/14（14%） |
| **可用率** | **12/14 = 86%** |
| 平均耗时 | 1.3-2.9 s/张 |

### 逐条结果

| # | 公式 | 判定 | 说明 |
|---|---|---|---|
| A1 | 二次公式 | 完全一致 | |
| A2 | 高斯积分 | 完全一致 | |
| A3 | 级数求和 | 语义等价 | `\underset{n=1}{\overset{\infty}{\sum}}` ≡ `\sum_{n=1}^{\infty}` |
| A4 | 极限 | 语义等价 | 后处理后 `\lim` 正确（原为 `l i m`） |
| B1 | 矩阵 | 语义等价 | `\left[\begin{matrix}\right]` ≡ `\begin{pmatrix}` |
| B2 | 分段函数 | **实质错误** | `=` 认成 `\neq`，cases 结构丢失 |
| B3 | 嵌套分数 | 完全一致 | |
| B4 | 张量方程 | 完全一致 | |
| C1 | 麦克斯韦 | **实质错误** | 粗体 `\mathbf{J}` → `\mathbf{\eta}` |
| C2 | 薛定谔 | 完全一致 | |
| C3 | 化学式 | 语义等价 | `\to` ≡ `\rightarrow` |
| D1 | 行列式 | 语义等价 | 符号全对，`\underset` 写法差异 |
| D2 | 正态分布 | 完全一致 | |
| D3 | 期望 | 语义等价 | 多了 `\boldsymbol` 粗体，语义不变 |

### 剩下 2 个错误分析

**B2 分段函数**
```
期望: f(x) = \begin{cases} x^2 & x \geq 0 \\ -x & x < 0 \end{cases}
识别: f(x) \neq\begin{matrix}{x^2} &{\mathrm{ x \ge0 }} \\ ... \end{matrix}
```
- `=` 误认成 `\neq`
- `\begin{cases}` 结构未识别，降级为 `matrix`
- **影响面小**：真实场景中分段函数出现频率低，且多数人用手写而非印刷

**C1 麦克斯韦方程**
```
期望: \mu_0 \mathbf{J}
识别: \mu_0 \mathbf{\eta}
```
- 粗体斜体的 J 与 η 视觉上高度相似
- **影响面**：仅物理/张量公式，理工科教材常见

---

## 三、后处理的作用

`src/postprocess.py` 修复的问题：

| 原始输出 | 修复后 |
|---|---|
| `\operatorname* {l i m}` | `\lim` |
| `\mathrm{s g n}` | `\operatorname{sgn}` |
| `\operatorname* {d e t}` | `\det` |
| `\frac{1} {2}` | `\frac{1}{2}` |
| `f ( x )` | `f(x)` |
| `\textstyle\int...` | `\int...` |

**效果**：从 8 张"格式错"降到 6 张完全一致 + 6 张语义等价。

---

## 四、环境依赖锁定（血泪教训）

| 组件 | 必须版本 | 不锁会怎样 |
|---|---|---|
| Python | **3.12** | 3.14+ 装不了 onnxruntime |
| rapidocr | **3.9.2** | 3.10+ 删了 `resolve_model_key`，cnstd 崩 |
| pix2text | 1.1.7 | 老版本 0.2.3.3 依赖损坏 |

验证失败的完整报错：
```
ImportError: cannot import name 'resolve_model_key'
from 'rapidocr.utils.model_resolver'
```

---

## 五、结论

**选用 P2T (pix2text 1.1.7) + Python 3.12 + rapidocr 3.9.2。**

理由：
1. 可用率 86% vs 21%，差距 4 倍
2. 错误类型更可控（空格 vs 符号错认）
3. 剩余错误可通过后处理与文档说明覆盖

**已知限制**（写入 README）：
- 分段函数结构识别不稳
- 粗体字母（mathbf）偶有混淆
- 不支持下划线、手写体
