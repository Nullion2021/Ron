# 麻将 AI 助手 (Ron)

基于深度学习和计算机视觉的麻将决策辅助系统，能够实时识别游戏状态并提供切牌策略建议。

## 项目概述

本项目旨在构建一个完整的麻将 AI 助手，包含以下核心模块：

- **核心模型训练 (The Brain)**：基于监督学习的深度学习模型，输入游戏状态，输出高质量切牌策略
- **视觉识别模块 (The Eyes)**：从屏幕像素中精准提取游戏状态信息
- **系统集成 (Integration)**：将视觉输入与模型输出连通，并提供可视化界面
- **进阶优化 (Advanced)**：强化学习、攻防判断等高级功能

---

## 第一阶段：核心模型训练 (The Brain)

**目标**：训练一个能够输入游戏状态（State），输出高质量切牌策略（Policy）的深度学习模型。

### 1. 数据准备 (Data Pipeline)

#### [x] 获取数据
- **下载天凤牌谱**：使用 `data/download_logs.py` 脚本自动下载天凤凤凰卓的牌谱日志
  - 可配置日期范围和每日下载数量限制
  - 自动处理 gzip 压缩文件
  - 支持断点续传（已下载的文件会自动跳过）
  
  **使用方法**：
  ```bash
  python data/download_logs.py
  ```
  
  **配置项**（在脚本开头修改）：
  - `START_DATE` / `END_DATE`：设置下载日期范围
  - `DOWNLOAD_LIMIT_PER_DAY`：每天下载数量（设为 `None` 下载全部）
  - `SAVE_DIR`：牌谱保存目录（默认 `./data/raw_mjlog`）

- 建议起步规模：1,000 ~ 10,000 局，跑通后扩展至百万级

#### [x] 数据清洗与转换
- **转换牌谱格式**：使用 `data/convert_to_json.py` 将天凤 `.mjlog` 格式转换为标准 JSON 格式
  - 自动检测并解压 gzip 文件
  - 解析 XML 结构的事件流
  - 转换牌代码（天凤 ID → 标准格式，如 `1m`, `5p`, `3z`）
  - 提取关键信息：初始手牌、场风、宝牌指示牌、鸣牌、立直、和牌等
  
  **使用方法**：
  ```bash
  python data/convert_to_json.py
  ```
  
  **输出格式**：
  - 每个牌谱转换为 JSON 数组，包含完整的事件流
  - 事件类型：`start_kyoku`, `tsumo`, `dahai`, `naki`, `reach`, `hora`, `ryukyoku`

- 使用 `mjx` 的转换工具读取牌谱（待实现）
- 将每一步操作拆解为 `(Observation, Action)` 对
- **Feature Engineering**：构建特征张量生成器
- 确保包含：手牌、副露、场风、自风、宝牌指示牌、所有玩家的弃牌池、剩余牌数

#### [ ] 构建 DataLoader
- 实现一个支持 Batch 读取的 Python 生成器
- 划分数据集：训练集 (Training Set) / 验证集 (Validation Set)

### 2. 模型架构搭建 (Architecture)

#### [ ] 选择框架
- 推荐使用 **JAX + Flax**（与 mjx 原生兼容）或 **PyTorch**

#### [ ] 定义网络结构
- **Input Layer**：维度通常为 `[Batch_Size, Channels, 34, 1]` 或类似结构
- **Backbone**：
  - 方案 A（轻量）：3-5 层 CNN
  - 方案 B（标准）：ResNet（残差网络），推荐 18 层或 50 层
- **Output Layer**：
  - 全连接层，输出维度 34（对应 34 种牌的打出概率 logits）
  - (可选) 增加吃、碰、杠、立直的决策输出分支

### 3. 监督学习训练 (Supervised Learning)

#### [ ] 定义损失函数 (Loss Function)
- 使用 `CrossEntropyLoss`（交叉熵）
- **关键步骤 - Masking**：实现 Action Mask 机制，在计算 Loss 前将非法动作（如手里没有的牌）的概率强制置为 0，防止模型学习无效动作

#### [ ] 执行训练
- 设置 Optimizer（如 Adam）
- 监控指标：Training Loss, Validation Accuracy（Top-1 准确率）
- 目标：Top-1 Accuracy 达到 60% 以上即可视为模型可用

### 4. 模型评估与封装 (Evaluation & API)

#### [ ] 基准测试
- 在 mjx 纯环境内，让模型与内置脚本（如 Shanten 向听数脚本）对战 100 局
- 统计：和牌率、放铳率、平均顺位

#### [ ] 推理接口封装
编写 Inference 类，实现以下标准接口：

```python
def predict(self, hand_tiles, discards, dora_markers, ...) -> dict:
    # 返回 { '1m': 0.02, '5z': 0.98, ... }
```

---

## 第二阶段：视觉识别模块 (The Eyes)

**目标**：从屏幕像素中精准提取游戏状态信息。

### 1. 屏幕捕获基础

#### [ ] 实现截图工具
- 使用 `mss` 库实现高频截图（>10 FPS）
- 适配雀魂网页版/客户端窗口坐标

#### [ ] 建立坐标映射表
- 硬编码各个区域的 ROI (Region of Interest)：手牌区、副露区、宝牌区、场风区

### 2. 图像识别系统

#### [ ] 素材库准备
- 截取雀魂标准牌面（1m-9m, 1p-9p, 1s-9s, 1z-7z）以及红宝牌
- 截取场风文字（东/南/西/北）

#### [ ] 牌面识别算法
- 实现 OpenCV 的 `matchTemplate`（模板匹配）
- 实现红宝牌识别（通常需要结合 HSV 颜色空间判断红色像素点）

#### [ ] OCR 文字识别
- 识别左上角的剩余局数、场况点数（使用 Tesseract 或 PaddleOCR）

### 3. 状态重构 (State Reconstruction)

#### [ ] 全量状态维护
- 编写一个 `GameWatcher` 类
- 由于单帧截图无法获取所有弃牌信息，需要根据每一帧的变化，逐步填充并维护一个"虚拟牌桌"状态

#### [ ] 数据结构对齐
- **最关键步骤**：将识别到的 Python 对象（如 `['1m', '2m']`）转换为第一阶段模型所需的 Tensor 格式

---

## 第三阶段：系统集成与交互 (Integration)

**目标**：将视觉输入与模型输出连通，并展示结果。

### 1. 主控制循环 (Main Loop)

#### [ ] 编写主程序

```python
while True:
    1. Capture Screen
    2. Update Game State (CV)
    3. if (My Turn):
           Tensor = State_to_Tensor(State)
           Action = Model.predict(Tensor)
           Display(Action)
    4. Sleep(0.5 s)
```

### 2. 用户界面 (Overlay)

#### [ ] 开发透明浮窗
- 使用 PyQt5 或 Tkinter 创建无边框、置顶、透明背景的窗口

#### [ ] 可视化输出
- 在手牌上方绘制推荐打出的牌及其概率条（Confidence Bar）
- 用不同颜色标记危险度（可选）

### 3. 性能优化

#### [ ] 延迟优化
- 确保从截图到输出建议的总耗时 < 200ms

#### [ ] 稳定性测试
- 连续运行 1 半庄，确保内存不泄露，识别不丢帧

---

## 第四阶段：进阶优化 (Advanced - Optional)

- **强化学习 (RL)**：在 SL 模型基础上，使用 PPO 算法进行自我博弈微调，提升胜率
- **攻防判断**：训练单独的"立直判断模型"和"鸣牌判断模型"
- **读牌辅助**：显示每张牌的安全度（通过计算对手听牌概率）

---

## 技术栈

### 核心依赖
- **深度学习框架**：JAX + Flax / PyTorch
- **麻将模拟**：mjx
- **计算机视觉**：OpenCV, mss
- **OCR**：Tesseract / PaddleOCR
- **GUI**：PyQt5 / Tkinter

### 数据来源
- 天凤（Tenhou）凤凰卓牌谱

---

## 项目结构

Ron/
├── README.md
├── data/              # 数据目录
│   ├── download_logs.py      # 天凤牌谱下载脚本
│   ├── convert_to_json.py    # 牌谱格式转换脚本
│   ├── raw_mjlog/            # 原始天凤牌谱 (.mjlog)
│   ├── json_logs/            # 转换后的牌谱 (.json)
│   ├── raw/                  # 原始牌谱（预留）
│   ├── processed/            # 处理后的数据
│   └── models/               # 训练好的模型
├── src/
│   ├── model/        # 核心模型模块
│   ├── vision/       # 视觉识别模块
│   └── integration/  # 系统集成模块
└── test/             # 测试脚本


---

## 开发进度

- [x] 项目规划与文档编写
- [ ] 第一阶段：核心模型训练
  - [x] 数据准备
    - [x] 牌谱下载工具 (`download_logs.py`)
    - [x] 牌谱格式转换工具 (`convert_to_json.py`)
  - [ ] 数据清洗与特征工程
  - [ ] 模型架构搭建
  - [ ] 监督学习训练
  - [ ] 模型评估与封装
- [ ] 第二阶段：视觉识别模块
  - [ ] 屏幕捕获基础
  - [ ] 图像识别系统
  - [ ] 状态重构
- [ ] 第三阶段：系统集成与交互
  - [ ] 主控制循环
  - [ ] 用户界面
  - [ ] 性能优化
- [ ] 第四阶段：进阶优化

---

## 项目日志

### 2026-02-06
- 实现天凤牌谱下载工具 ([`download_logs.py`](data/download_logs.py))
- 实现牌谱格式转换工具 ([`convert_to_json.py`](data/convert_to_json.py))
- 下载并转换 113 个天凤牌谱文件

---

## 贡献指南

欢迎提交 Issue 和 Pull Request！

## 许可证

待定

---

**注意**：本工具仅供学习和研究使用，请勿用于任何形式的作弊或违反游戏服务条款的行为。