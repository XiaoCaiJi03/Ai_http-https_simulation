# 网络安全仿真平台 - 项目文档

## 一、项目整体架构说明

### 1.1 项目概述

本项目是一个网络安全仿真与分析平台，提供 HTTP/TCP 协议仿真、TLS/SSL 安全分析、证书生成与检测、流量劫持仿真、AI 智能报文分析、恶意流量检测等核心功能。

### 1.2 技术栈

| 层级 | 技术选型 | 说明 |
|------|---------|------|
| 前端 | Vue 3 + Vite + Element Plus + ECharts | 单页应用，提供可视化交互界面 |
| 后端 | Python (Flask + Waitress) | 主服务，提供 RESTful API |
| 微服务 | Go (net包原生HTTP) | 压测工具 bench，高性能并发测试 |
| 通信 | HTTP REST API | 前后端通过 JSON 格式通信 |

### 1.3 架构图

```
┌─────────────────────────────────────────────┐
│                  前端 (Vue 3)                │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌──────┐       │
│  │协议仿真│ │安全仿真│ │AI分析│ │恶意检测│      │
│  └──┬───┘ └──┬───┘ └──┬───┘ └──┬───┘       │
│     └────────┴────────┴────────┘            │
│              utils/request.js                │
└──────────────────┬──────────────────────────┘
                   │ HTTP REST API (JSON)
┌──────────────────┴──────────────────────────┐
│              后端 (Python Flask)              │
│  ┌──────────────────────────────────────┐   │
│  │            app.py (主路由)             │   │
│  └──────┬──────┬──────┬──────┬──────────┘   │
│  ┌──────┴──┐ ┌─┴────┐ ┌┴─────┐ ┌┴────────┐  │
│  │respond  │ │security│ │ai_   │ │malicious│  │
│  │.py      │ │.py    │ │analyze│ │_detector│  │
│  │HTTP仿真 │ │TLS/证书│ │.py   │ │.py      │  │
│  └─────────┘ └───────┘ └──────┘ └─────────┘  │
│  ┌──────────────────────────────────────┐   │
│  │      big_simulator.py (压测调度)       │   │
│  └──────────────┬───────────────────────┘   │
└─────────────────┼───────────────────────────┘
                  │ 子进程调用
┌─────────────────┴───────────────────────────┐
│           Go 压测工具 (bench)                │
│     高性能 HTTP 并发压测，输出 JSON 结果       │
└─────────────────────────────────────────────┘
```

### 1.4 目录结构

```
combie_1/
├── front/                    # 前端 Vue 3 项目
│   ├── src/
│   │   ├── pages/           # 页面组件
│   │   ├── components/      # 公共组件
│   │   ├── router/          # 路由配置
│   │   ├── store/           # 状态管理
│   │   ├── utils/           # 工具函数
│   │   ├── App.vue          # 根组件
│   │   └── main.js          # 入口文件
│   ├── vite.config.js       # Vite 构建配置
│   └── package.json         # 前端依赖
├── back/                     # 后端 Python 项目
│   ├── app.py               # 主应用入口 & 路由
│   ├── src/
│   │   ├── __init__.py      # 模块导出
│   │   ├── respond.py       # HTTP/TCP 协议仿真
│   │   ├── security.py      # TLS/SSL 安全仿真
│   │   ├── ai_analyze.py    # AI 智能分析
│   │   ├── big_simulator.py # 压测调度器
│   │   ├── malicious_detector.py # 恶意流量检测
│   │   └── benfen/          # 辅助模块
│   │       ├── cert_generator.py   # 证书生成器
│   │       ├── hijack_simulator.py # 劫持仿真器
│   │       ├── pcap_to_json.py     # PCAP 转 JSON
│   │       ├── app_ai.py           # AI 分析辅助
│   │       └── ubuntu.py           # 服务器管理
│   ├── bench/               # Go 压测工具
│   │   ├── bench.go         # Go 源码
│   │   └── go.mod           # Go 模块定义
│   ├── data/                # 运行时数据目录
│   ├── requirements.txt     # Python 依赖
│   └── Dockerfile           # 容器构建文件
└── docker-compose.yml       # Docker 编排配置
```

---

## 二、各模块功能说明与接口文档

### 2.1 前端模块

#### 页面组件

| 页面 | 文件 | 功能 |
|------|------|------|
| 协议仿真 | SimulationPage.vue | HTTP/TCP 请求响应仿真，支持自定义请求头和请求体 |
| 安全仿真 | SecuritySimulation.vue | TLS 1.3 握手仿真、证书生成与检测、劫持仿真 |
| AI 分析 | Ai_analyze.vue | AI 智能报文分析，支持自然语言交互 |
| 恶意检测 | MaliciousAnalysis.vue | 恶意流量检测与可视化分析 |
| 大并发压测 | Big.vue | HTTP 大并发压测，实时展示 QPS/延迟等指标 |
| 历史记录 | HistoryPage.vue | 证书生成记录与压测历史查看 |
| HTTP/TCP | HttpTcp.vue | HTTP 与 TCP 协议对比演示 |

#### 公共组件

| 组件 | 文件 | 功能 |
|------|------|------|
| Cookie 查看器 | CookieViewer.vue | 解析和展示 HTTP Cookie 信息 |
| SSL 握手 | SSLHandshake.vue | SSL/TLS 握手过程可视化 |
| JSON 查看器 | JsonViewerAdapter.vue | JSON 数据格式化展示（预留） |

#### 工具模块

| 模块 | 文件 | 功能 |
|------|------|------|
| HTTP 请求 | utils/request.js | Axios 封装，统一 baseURL、拦截器、错误处理 |
| 通用工具 | utils/common.js | URL 验证、格式化等通用函数 |
| 路由 | router/index.js | Vue Router 路由配置 |
| 状态管理 | store/index.js | Pinia 状态管理 |

### 2.2 后端 API 接口

#### 协议仿真接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/simulate | HTTP 仿真请求，返回响应内容 |
| POST | /api/simulate/concurrent | 并发仿真请求 |
| GET | /api/simulate/tshark | 检查 tshark 是否可用 |
| POST | /api/simulate/test-capture | 测试抓包功能 |

#### 安全仿真接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/security/tls13/simulate | TLS 1.3 握手仿真 |
| POST | /api/security/hijack/simulate | 流量劫持仿真 |
| POST | /api/security/cert/generate | 生成证书（自签名/CA/过期/弱密钥） |
| GET | /api/security/cert/list | 获取已生成证书列表 |
| POST | /api/security/cert/content | 获取证书文件内容 |

#### 压测接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/big/simulate | 启动大并发压测 |
| GET | /api/big/status | 获取压测运行状态 |

#### AI 分析接口

| 方法 | 路径 | 说明 |
|------|------|------|
| POST | /api/ai/analyze | AI 分析 HTTP 请求/响应 |

#### 历史记录接口

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | /api/logs/cert/list | 证书生成历史列表 |
| GET | /api/logs/big-concurrent/list | 压测历史列表 |
| GET | /api/history/list | 通用历史记录列表（支持分页） |

### 2.3 Go 压测工具 (bench)

命令行工具，通过子进程方式被 Python 后端调用。

```bash
bench -c <并发数> -t <时长秒> -url <目标URL> -json
```

| 参数 | 默认值 | 说明 |
|------|--------|------|
| -c | 100 | 并发连接数 |
| -t | 10 | 测试时长（秒） |
| -url | http://localhost:80 | 目标 URL |
| -json | false | 输出 JSON 格式结果 |

输出指标：总请求数、成功/失败数、QPS、平均延迟、P50/P90/P99 延迟、吞吐量。

---

## 三、问题修复清单及修复思路

### 3.1 关键 (Critical) 修复

| 编号 | 问题 | 文件 | 修复思路 |
|------|------|------|---------|
| C1 | 硬编码 API 密钥泄露 | ai_analyze.py | 移除默认值，改为环境变量读取 + 启动检查 + None 保护 |
| C2 | 路径遍历漏洞（3处） | app.py, security.py, app_ai.py | 添加 os.path.basename() + `..` 检查 + 路径白名单校验 |
| C3 | 命令注入风险（3处） | big_simulator.py, ubuntu.py | URL 正则验证；shell=True→列表形式；os.system→subprocess.run |
| C4 | CORS 配置错误 | app.py | 移除与 origins:"*" 不兼容的 supports_credentials |
| C5 | 重复 Flask 应用与路由冲突 | security.py | 移除独立 Flask app 及路由，仅保留类定义 |
| C6 | TLS 验证禁用无注释 | respond.py, security.py | 添加安全警告注释说明仅用于仿真环境 |
| C7 | SSLKEYLOGFILE 影响全局 | security.py | 添加安全警告注释 |
| C8 | XSS 跨站脚本攻击 | Big.vue, Ai_analyze.vue, SimulationPage.vue, CookieViewer.vue | v-html→文本插值/HTML转义；移除 dangerouslyUseHTMLString |
| C9 | 硬编码 API 地址 | 多个前端页面 | 统一使用 utils/request.js 封装的 axios 实例 |
| C10 | 全局 axios 配置互相覆盖 | 多个前端页面 | 各页面不再修改 axios.defaults，使用独立 request 实例 |
| C11 | 路由重复定义 | router/index.js | 删除重复的 /Ai_analyze 路由 |
| C12 | 缺失 import 导致崩溃 | SSLHandshake.vue | 添加 watchEffect 到 vue 导入 |
| C13 | Props 与 ref 命名冲突 | SSLHandshake.vue | 重命名本地 ref，添加 watch 同步 props |
| C14 | CRLF 注入漏洞 | bench.go | 添加 \r\n 字符检查 |
| C15 | 响应字节数硬编码 | bench.go | 改为追踪实际读取字节数 |
| C16 | 响应失败未计数 | bench.go | 添加 failed 计数器递增 |

### 3.2 高优先级 (High) 修复

| 编号 | 问题 | 文件 | 修复思路 |
|------|------|------|---------|
| H1 | 导入错误导致启动失败 | app_ai.py | 修正导入名称匹配实际导出 |
| H2 | 导入不存在的类 | app_ai.py | BigSimulator→run_big_simulation |
| H3 | __init__.py 导出不匹配 | __init__.py | 更新导出列表 |
| H4 | 连接池线程安全 | respond.py | 添加 threading.Lock |
| H5 | 内存泄漏 | security.py | 添加 MAX_HIJACK_ATTEMPTS 上限 |
| H6 | 历史记录无分页 | app.py | 添加 page/page_size 参数 |
| H7 | stdout 可能为 None | big_simulator.py | 添加 None 检查 |
| H8 | 整数转换无异常处理 | app.py | 添加 try/except |
| H9 | 包名错误 | requirements.txt | scikit_learn→scikit-learn |
| H10 | 依赖版本过旧 | requirements.txt | cryptography 升级 |
| H11 | HTTP 状态码解析脆弱 | bench.go | 使用 strings.Fields 正确解析 |
| H12 | int64 截断溢出 | bench.go | 添加溢出检查 |
| H13 | 初始连接失败永久退出 | bench.go | 添加重试逻辑 |
| H14 | URL 解析器功能不足 | bench.go | 添加 fragment 剥离和默认端口 |
| H15 | request.js 未被使用 | 多个前端页面 | 统一使用 request.js 实例 |
| H16 | 定时器未清理 | SimulationPage.vue, Big.vue | 保存 ID + onUnmounted 清理 |

### 3.3 中等优先级 (Medium) 修复

| 编号 | 问题 | 修复思路 |
|------|------|---------|
| M1 | 重复导入 | 移除重复导入 |
| M2 | 未使用导入 | 清理未使用的 import |
| M3 | datetime.utcnow() 弃用 | 改为 datetime.now(timezone.utc) |
| M4 | 裸 except 语句 | 改为 except Exception |
| M5 | 文件未指定编码 | 添加 encoding='utf-8' |
| M6 | handle_concurrent_simulation 返回空 | 返回含 message 的字典 |
| M7 | 错误详情暴露给客户端 | 移除堆栈信息 |
| M8 | KeyError 风险 | 添加键存在性检查 |
| M9 | None 判断方式 | if not→if is None |
| M10 | 死代码 | 移除空壳方法 |
| M11 | MockLogger | 改用标准 logging |
| M12 | 函数内导入 | 移至文件顶部 |
| M13 | set_ecdh_curve 不存在 | 改用 set_ciphers |
| M14 | Cookie 解析缺陷 | 用 indexOf+substring 替代 split |
| M15 | URL 正则过严 | 支持端口/IP/长TLD |
| M16 | 模拟数据残留 | 删除 mock 数据 |
| M17 | chunk 解析错误忽略 | bench.go 添加错误处理 |
| M18 | 速度指标单位 | pages/min→reqs/sec |

### 3.4 低优先级 (Low) 修复

| 编号 | 问题 | 修复思路 |
|------|------|---------|
| L1 | 未使用变量/函数 | 删除 |
| L2 | 注释掉的死代码 | 清理 |
| L3 | 路由命名不一致 | 统一为 kebab-case |
| L4 | rollup 不应在 dependencies | 移除 |
| L5 | DOM 操作时序 | 包裹在 nextTick |
| L6 | 缺少 404 路由 | 添加兜底路由 |
| L7 | 默认并发数过高 | 1000→100 |
| L8 | go.mod 模块名过通用 | bench→combie/bench |
| L9 | 请求报文重复构建 | 预构建共享 |
| L10 | 误导性注释 | 修正/移除 |

---

## 四、项目部署与运行操作指南

### 4.1 环境要求

- **Node.js**: >= 16.x
- **Python**: >= 3.9
- **Go**: >= 1.21
- **Wireshark/tshark**: 用于抓包分析（可选）

### 4.2 前端部署

```bash
# 进入前端目录
cd front

# 安装依赖
npm install

# 开发模式运行
npm run dev

# 生产构建
npm run build
# 构建产物在 dist/ 目录
```

### 4.3 后端部署

```bash
# 进入后端目录
cd back

# 创建虚拟环境（推荐）
python -m venv venv
# Windows 激活
venv\Scripts\activate
# Linux 激活
source venv/bin/activate

# 安装依赖
pip install -r requirements.txt

# 编译 Go 压测工具
cd bench
go build -o bench.exe bench.go
cd ..

# 设置环境变量
set ARK_API_KEY=你的火山引擎API密钥
set TSHARK_PATH=E:\Program Files\Wireshark\tshark.exe

# 启动服务
python app.py
# 服务默认运行在 http://0.0.0.0:60110
```

### 4.4 Docker 部署（参考）

```bash
# 在项目根目录
docker-compose up -d
```

### 4.5 开发环境代理配置

前端开发时，Vite 已配置代理将 `/api` 请求转发到后端 `localhost:60110`，无需额外配置。

---

## 五、开发环境配置说明

### 5.1 前端配置

| 配置项 | 文件 | 说明 |
|--------|------|------|
| API 代理 | vite.config.js | `/api` → `http://localhost:60110` |
| API 基础路径 | utils/request.js | baseURL 默认为 `/`，通过代理转发 |
| 环境变量 | .env.development | `VITE_API_BASE_URL` 可覆盖默认值 |

### 5.2 后端配置

| 配置项 | 环境变量 | 默认值 | 说明 |
|--------|---------|--------|------|
| AI API 密钥 | ARK_API_KEY | 无（必填） | 火山引擎 Ark API 密钥 |
| tshark 路径 | TSHARK_PATH | 无 | Wireshark tshark 可执行文件路径 |
| 服务端口 | - | 60110 | Waitress 监听端口 |
| 服务线程 | - | 256 | Waitress 工作线程数 |

### 5.3 Go 压测工具配置

通过命令行参数配置，详见 2.3 节。

### 5.4 关键依赖版本

**Python 后端：**
- Flask >= 3.0
- flask-cors >= 4.0
- waitress >= 2.1
- cryptography >= 42.0
- scikit-learn >= 1.3
- requests >= 2.31

**前端：**
- Vue 3.x
- Element Plus
- ECharts 5.x
- Axios

**Go：**
- Go 1.21+（仅使用标准库）
