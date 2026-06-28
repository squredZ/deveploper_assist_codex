# 特性知识与 Hilog 分析 Agent 设计文档

## 1. 背景

排查系统功能问题时，研发通常需要同时理解功能设计、调用链、本地代码位置、关键接口、关键日志和问题发生时间附近的 hilog。信息分散在代码、日志、文档和个人经验中，人工排查成本高。

本 Agent 基于提前生成的 `feature.yaml`，结合本地代码和 hilog 日志，提供特性问答、日志自动分析和 `feature.yaml` 维护辅助能力。

## 2. 目标

MVP 阶段实现一个 CLI 可执行程序，支持三类能力：

1. 特性知识问答：用户选择功能特性并提问，Agent 基于 `feature.yaml` 和必要的本地代码给出分析。
2. Hilog 自动分析：用户提供 hilog 文件或压缩包、问题发生时间和时间窗口，Agent 自动过滤日志、匹配特性并分析可能根因。
3. `feature.yaml` 维护辅助：用户输入模块名和模块代码路径，Agent 分析模块代码并输出新增或删除模块的 yaml patch 建议。

## 3. 非目标

MVP 阶段暂不实现：

- Web UI
- 自动修复代码
- 自动提交 patch
- 多 Agent 协作
- 向量数据库
- 全仓库知识图谱
- 复杂插件市场
- 自动长期记忆系统

这些能力等 MVP 跑通真实案例后再评估。

## 4. 使用方式

第一版使用 CLI。

### 4.1 特性问答

```bash
agent ask \
  --feature camera_capture \
  --question "拍照不出图可能是什么原因"
```

### 4.2 Hilog 分析

```bash
agent analyze-log \
  --log /path/to/hilog.zip \
  --time "2026-06-28 14:35" \
  --window 60 \
  --question "拍照不出图" \
  --feature camera_capture
```

`--feature` 可选。用户不提供时，Agent 根据问题和日志匹配候选特性。

### 4.3 新增模块到 feature.yaml

```bash
agent add-module \
  --feature camera_capture \
  --module image_pipeline \
  --path foundation/multimedia/image_pipeline
```

### 4.4 删除模块

```bash
agent remove-module \
  --feature camera_capture \
  --module image_pipeline
```

MVP 阶段不直接写 `feature.yaml`，只输出 patch 建议。

## 5. 总体架构

```text
CLI
 |
 v
Agent Orchestrator
 |
 +-- FeatureStore
 +-- HilogAnalyzer
 +-- CodeReader
 +-- EvidenceMatcher
 +-- Reasoner
```

### 5.1 模块职责

| 模块 | 职责 |
| --- | --- |
| CLI | 解析命令行参数，调用对应任务 |
| Agent Orchestrator | 编排工具调用，组织上下文 |
| FeatureStore | 读取、校验、渲染 `feature.yaml` |
| HilogAnalyzer | 解压日志、解析日志、按时间过滤 |
| CodeReader | 读取文件、搜索代码、定位 symbol |
| EvidenceMatcher | 将日志和 `feature.yaml` 中的 pattern 匹配 |
| Reasoner | 基于 feature、日志、代码证据输出分析 |

## 6. 目录结构

第一版保持简单：

```text
agent/
  main.py
  feature.py
  hilog.py
  code.py
  matcher.py
  analyze.py
  schema.py

features/
  camera_capture.yaml

tests/
  test_hilog.py
  test_feature.py
```

## 7. Feature.yaml 设计

`feature.yaml` 是 Agent 的核心数据源，不只是说明文档，而是排障索引。

### 7.1 示例

```yaml
name: camera_capture
display_name: 相机拍照
description: 拍照功能链路，包括 UI 触发、相机会话、拍照请求、图像回调、保存与展示

keywords:
  - 拍照
  - 出图
  - capture
  - take picture
  - camera

modules:
  - name: camera_ui
    path: applications/camera
    responsibility: 拍照入口、UI 状态、拍照结果展示

  - name: camera_framework
    path: foundation/multimedia/camera_framework
    responsibility: 相机会话、拍照请求、回调分发

  - name: media_store
    path: foundation/multimedia/media_library
    responsibility: 图片保存、媒体库入库

entrypoints:
  - name: 用户点击拍照
    module: camera_ui
    file: applications/camera/src/photo/PhotoPage.ts
    symbol: onShutterClick
    description: UI 侧拍照入口

call_chains:
  - name: normal_capture
    description: 正常拍照链路
    steps:
      - id: ui_click
        module: camera_ui
        file: applications/camera/src/photo/PhotoPage.ts
        symbol: onShutterClick
        description: 用户点击拍照按钮
        expected_logs:
          - tag: CameraUI
            pattern: click capture

      - id: capture_request
        module: camera_framework
        file: foundation/multimedia/camera_framework/services/capture_session.cpp
        symbol: CaptureSession::Capture
        description: 发起拍照请求
        expected_logs:
          - tag: CameraService
            pattern: Start capture

      - id: image_callback
        module: camera_framework
        symbol: OnImageAvailable
        description: 收到拍照图像回调
        expected_logs:
          - tag: ImageReceiver
            pattern: OnImageAvailable

      - id: save_result
        module: media_store
        symbol: SavePhoto
        description: 保存图片并通知 UI 展示
        expected_logs:
          - tag: MediaStore
            pattern: save image

failure_patterns:
  - symptom: 拍照不出图
    related_steps:
      - capture_request
      - image_callback
      - save_result
    key_logs:
      - tag: CameraService
        level: ERROR
        pattern: Capture failed
        meaning: 拍照请求失败
      - tag: ImageReceiver
        level: WARN
        pattern: no image available
        meaning: 没有收到图像数据
      - tag: MediaStore
        level: ERROR
        pattern: save failed
        meaning: 图片保存失败
    possible_causes:
      - 相机会话未 ready
      - capture 请求失败
      - 图像回调未触发
      - buffer queue 异常
      - 图片保存失败
      - UI 未正确展示结果
```

### 7.2 字段说明

| 字段 | 必填 | 说明 |
| --- | --- | --- |
| name | 是 | 特性唯一标识 |
| display_name | 是 | 展示名 |
| description | 是 | 功能描述 |
| keywords | 是 | 用于问题和日志匹配 |
| modules | 是 | 功能涉及模块 |
| entrypoints | 否 | 关键入口 |
| call_chains | 是 | 关键调用链 |
| failure_patterns | 是 | 常见故障模式 |

## 8. 工具设计

MVP 只保留必要工具。

### 8.1 Feature 工具

```text
list_features()
read_feature(name)
validate_feature(feature_yaml)
render_feature_patch(old_yaml, new_yaml)
```

### 8.2 Code 工具

```text
read_file(path, start_line?, end_line?)
search_code(path, keyword)
search_logs_in_code(path)
```

### 8.3 Hilog 工具

```text
unpack_log(path)
filter_hilog_by_time(path, center_time, window_seconds)
match_logs_by_patterns(events, patterns)
```

### 8.4 分析逻辑

MVP 先放在主流程中，不单独做外部工具：

```text
rank_features(question, events, features)
analyze_with_evidence(question, feature_yaml, matched_logs, code_snippets)
```

## 9. 特性问答流程

### 9.1 输入

```json
{
  "feature": "camera_capture",
  "question": "拍照不出图可能是什么原因"
}
```

### 9.2 流程

```text
1. read_feature(camera_capture)
2. 根据 question 匹配 failure_patterns.symptom
3. 找到相关 call_chain steps
4. 汇总 expected_logs、key_logs、possible_causes
5. 如需要，读取相关代码文件
6. 输出链路级分析
```

### 9.3 输出示例

```text
结论：
拍照不出图通常要优先排查 capture_request、image_callback、save_result 三段链路。

可能原因：
1. Capture 请求失败
   证据日志：CameraService / Capture failed
   相关链路：capture_request

2. 图像回调没有回来
   证据日志：ImageReceiver / no image available
   相关链路：image_callback

3. 图片保存失败
   证据日志：MediaStore / save failed
   相关链路：save_result

建议查看：
- CameraService 是否出现 Start capture 和 Capture failed
- ImageReceiver 是否出现 OnImageAvailable
- MediaStore 是否出现 save image 或 save failed
```

## 10. Hilog 自动分析流程

### 10.1 输入

```json
{
  "log_path": "/path/to/hilog.zip",
  "question": "拍照不出图",
  "center_time": "2026-06-28 14:35",
  "window_seconds": 60,
  "feature": "camera_capture"
}
```

### 10.2 流程

```text
1. unpack_log(log_path)
2. filter_hilog_by_time(center_time, window_seconds)
3. 如果 feature 为空，rank_features(question, logs)
4. read_feature(feature)
5. 提取 expected_logs 和 failure_patterns.key_logs
6. match_logs_by_patterns(events, patterns)
7. 按 call_chain 判断每一步是否有证据
8. 识别缺失日志
9. 必要时读取相关代码
10. 输出根因假设
```

### 10.3 日志证据类型

Agent 需要识别两类证据：

- 出现的异常日志：例如 `Capture failed`，直接指向失败原因。
- 缺失的关键日志：例如有 `Start capture`，但没有 `OnImageAvailable`，说明链路可能断在 image callback 前后。

### 10.4 输出示例

```text
结论：
更像是 image_callback 阶段异常，置信度：中。

证据：
- 14:35:01.120 CameraUI: click capture
- 14:35:01.350 CameraService: Start capture
- 14:35:02.010 CameraService: Capture success
- 未发现 ImageReceiver: OnImageAvailable
- 14:35:03.500 ImageReceiver: no image available

链路判断：
- ui_click：正常
- capture_request：正常
- image_callback：异常
- save_result：未进入

可能原因：
1. ImageReceiver 未正确注册
2. buffer queue 异常
3. Capture 控制面成功，但数据面没有返回图像

建议继续查看：
- ImageReceiver 初始化逻辑
- CaptureSession 到 ImageReceiver 的回调注册
- 相关代码：foundation/multimedia/camera_framework/...
```

## 11. Feature.yaml 维护流程

### 11.1 新增模块

输入：

```json
{
  "feature": "camera_capture",
  "module_name": "image_pipeline",
  "module_path": "foundation/multimedia/image_pipeline"
}
```

流程：

```text
1. read_feature(camera_capture)
2. search_code(module_path, 日志宏 / class / public 方法)
3. 提取候选类名、函数名、日志 tag、错误日志
4. 生成 module 草案
5. 生成 call_chain step 建议
6. 输出 yaml patch
```

输出示例：

```yaml
modules:
  - name: image_pipeline
    path: foundation/multimedia/image_pipeline
    responsibility: 图像接收、buffer 处理、图像回调

call_chains:
  - name: normal_capture
    steps:
      - id: image_pipeline_process
        module: image_pipeline
        symbol: ImageProcessor::Process
        description: 处理拍照图像数据
        expected_logs:
          - tag: ImagePipeline
            pattern: process image
```

### 11.2 删除模块

输入：

```json
{
  "feature": "camera_capture",
  "module_name": "image_pipeline"
}
```

流程：

```text
1. read_feature(camera_capture)
2. 查找 modules 中对应模块
3. 查找 call_chains 中引用该模块的 step
4. 查找 failure_patterns 中相关日志
5. 输出待删除或待确认 patch
```

不建议静默删除，因为调用链可能需要替换而不是删除。

## 12. Tool 管理设计

需要 tool 管理，但只做薄层。

### 12.1 Tool Registry

记录工具名、输入、输出、安全级别。

```yaml
tools:
  read_feature:
    safe: true
    input:
      feature: string
    output:
      feature_yaml: object

  search_code:
    safe: true
    input:
      path: string
      keyword: string
    output:
      matches: list

  filter_hilog_by_time:
    safe: true
    input:
      path: string
      center_time: string
      window_seconds: int
    output:
      events: list

  render_feature_patch:
    safe: true
    input:
      old_yaml: object
      new_yaml: object
    output:
      patch: string
```

### 12.2 权限原则

- 读文件允许
- 搜索代码允许
- 解压日志只允许到临时目录
- 修改 `feature.yaml` 前必须展示 diff
- MVP 不允许自动改业务代码

## 13. 关键实现细节

### 13.1 Hilog 解析

MVP 先支持常见 hilog 格式：

```text
06-28 14:35:01.120  1234  5678 I CameraService: Start capture
```

解析字段：

```json
{
  "time": "2026-06-28 14:35:01.120",
  "pid": "1234",
  "tid": "5678",
  "level": "I",
  "tag": "CameraService",
  "message": "Start capture",
  "raw": "原始日志行"
}
```

### 13.2 时间窗口

用户输入：

```text
center_time = 2026-06-28 14:35
window_seconds = 60
```

实际窗口：

```text
2026-06-28 14:34:00 到 2026-06-28 14:36:00
```

### 13.3 Feature 自动匹配

如果用户未指定 feature，按简单评分：

```text
score =
  question 命中 keywords 次数 * 3
+ logs 命中 key_logs.pattern 次数 * 5
+ logs 命中 tag 次数 * 2
```

分数最高的作为候选。MVP 不需要向量库。

### 13.4 置信度

```text
高：
- 明确异常日志命中 failure_patterns.key_logs
- 且链路断点清晰

中：
- 关键正常日志出现
- 后续 expected log 缺失
- 有少量异常日志

低：
- 只有关键词匹配
- 缺少直接日志证据
```

## 14. 错误处理

| 场景 | 处理 |
| --- | --- |
| feature 不存在 | 提示可用 feature 列表 |
| `feature.yaml` 格式错误 | 输出校验失败字段 |
| log 路径不存在 | 直接报错 |
| zip 解压失败 | 提示压缩包不可读 |
| 时间格式错误 | 提示正确格式 |
| 时间窗口内无日志 | 提示扩大窗口 |
| 未匹配到 feature | 要求用户指定 feature |
| 代码路径不存在 | 在输出中标记无法读取代码 |

## 15. MVP 验收标准

### Case 1：特性问答

输入：

```bash
agent ask --feature camera_capture --question "拍照不出图可能是什么原因"
```

预期：

- 能读取 `camera_capture.yaml`
- 能输出可能原因
- 能列出关键日志
- 能指出相关链路 step

### Case 2：Hilog 分析

输入：

```bash
agent analyze-log --log ./hilog.zip --time "2026-06-28 14:35" --window 60 --question "拍照不出图"
```

预期：

- 能解压日志
- 能过滤时间窗口
- 能匹配 feature
- 能匹配关键日志
- 能判断链路断点
- 能输出根因假设和证据

### Case 3：新增模块

输入：

```bash
agent add-module --feature camera_capture --module image_pipeline --path foundation/multimedia/image_pipeline
```

预期：

- 能扫描模块路径
- 能提取日志 tag 和关键函数
- 能输出 `feature.yaml` patch 建议

### Case 4：删除模块

输入：

```bash
agent remove-module --feature camera_capture --module image_pipeline
```

预期：

- 能找出模块引用
- 能输出需要删除或确认的 yaml 片段
- 不直接静默修改文件

## 16. 后续演进

MVP 稳定后再考虑：

1. Web UI
2. 自动写入 `feature.yaml`
3. 更强的代码 symbol 分析
4. 日志聚类
5. 多 feature 关联分析
6. 向量检索
7. 自动生成 `feature.yaml` 初稿
8. 和代码仓、构建系统、问题单系统集成

## 17. 推荐实现顺序

```text
1. 定义 feature.yaml schema
2. 实现 read_feature / validate_feature
3. 实现 ask 命令
4. 实现 hilog 解压和时间过滤
5. 实现日志 pattern 匹配
6. 实现 analyze-log 命令
7. 实现 search_code / read_file
8. 实现 add-module patch 输出
9. 实现 remove-module patch 输出
```

先完成这条主线，跳过复杂平台能力，等真实日志和真实 `feature.yaml` 跑完再加。
