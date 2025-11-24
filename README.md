
# 🌉 headless-bridge

> **The "Ghost" Gateway for Interactive CLIs in Kubernetes.**
> 让那些依赖“人类操作”的 CLI 工具，在无头 K8s 环境中获得永生。

![Version](https://img.shields.io/badge/version-v14-blue) ![Status](https://img.shields.io/badge/status-stable-green) ![License](https://img.shields.io/badge/license-MIT-orange)

## 📖 简介 (Introduction)

**headless-bridge** 解决了一个云原生时代的典型矛盾：

* **痛点**：许多强大的开发者工具（如 OpenAI Codex CLI, Vercel CLI, Telegram Client）设计初衷是**“本地优先”**的。它们依赖浏览器弹出验证、依赖本地文件系统、依赖人类的点击。
* **后果**：当你试图将 Agent 部署到云端（K8s/Docker）实现 24/7 自动化时，这些工具会因为没有 GUI 环境（Headless）而立刻崩溃。

**本项目是这一问题的通用解决方案。** 目前版本提供了 **OpenAI Codex Cloud** 的完整桥接实现。

### 📂 项目结构 (Project Layout)

```
headless-bridge/
├── core/                  # 框架核心：FastAPI 启动器 & 配置
│   ├── server.py          # Health / Auth Mount 检查入口
│   └── config.py          # 环境变量解析 (HB_* 前缀)
├── adapters/              # 插件区：按 CLI 类型扩展
│   └── codex/             # Codex 适配器
│       └── handler.py     # Prompt 与 CLI 调用
├── k8s/                   # 部署模板
│   └── deployment.yaml    # 默认 Deployment + Service
├── scripts/               # 工具脚本
│   └── rget               # 弹性下载工具
└── main.py                # 入口：装配 FastAPI 应用
```

## 🏗 架构 (Architecture)

我们通过“凭证外科手术”和“沙箱穿透”，将本地的交互状态移植到云端。

```mermaid
graph LR
    User[Local User] -- 1. Login (Interactive) --> AuthFile[auth.json]
    AuthFile -- 2. Inject (k8s Secret) --> K8s[Kubernetes Cluster]
    
    subgraph "Headless Bridge Pod"
        API[FastAPI Gateway]
        CLI[Interactive CLI Tool]
        API -- "3. Trigger" --> CLI
        CLI -- "4. SubPath Mount" --> Creds(Mapped Auth)
    end
    
    K8s --> API
    Agent[AI Agent] -- "REST API" --> API
    CLI -- "5. Execution" --> Cloud[Upstream Cloud (Codex/SaaS)]
````

## ⚡️ 核心黑科技 (Core Mechanics)

1.  **凭证心脏移植 (Auth Volume Injection)**
    利用 Kubernetes `subPath` 挂载技术，精准地将本地生成的凭证文件（如 `auth.json`）“手术式”植入到容器内的特定路径。欺骗 CLI 以为自己运行在已登录的本地电脑上。

2.  **YOLO 模式 (Safety Valve Bypass)**
    针对像 Codex 这种试图在容器内再起沙箱（Inception 架构）的工具，我们默认开启 `--dangerously-bypass-approvals-and-sandbox`。

      * *哲学*：在 K8s 中，**Pod 即沙箱**。我们利用外层 Pod 的隔离性，换取内部运行的稳定性。

3.  **HTTP 契约化 (Contract over CLI)**
    将不可控的 `stdout/stderr` 流，封装为结构化的 JSON 响应。让 LangChain、AutoGPT 等 Agent 可以像调用 API 一样调用 CLI。

-----

## 🚀 快速开始 (Quick Start)

### 1\. 本地取火 (Acquire Credentials)

在你的本地机器（有浏览器环境）完成首次登录。

```bash
# 本地运行
codex login
# 登录成功后，保存生成的 auth.json 文件
```

### 2\. 生成密钥 (Inject to K8s)

使用我们要提供的脚本，一键将凭证转化为 K8s Secret。

```bash
./scripts/generate_auth_secret.sh ./path/to/auth.json
```

### 3\. 启动桥接 (Deploy Bridge)

```bash
kubectl apply -f k8s/deployment.yaml
```

-----

## 🔌 接口定义 (API Reference)

服务默认暴露在端口 `8000`。

### 1\. 启动会话 (Run Session)

**POST** `/run_codex_session`

Agent 通过此接口驱动 Codex 进行“自动编程”或“环境修复”。

**Request:**

```json
{
  "contract_id": "task-2025-beta",
  "repo_url": "[https://github.com/ak-ooda/target-repo](https://github.com/ak-ooda/target-repo)",
  "failure_details": "Fix the login bug in main.py",
  "ak_url": "[https://files.ak-ooda.dev/tools/ak-cli-v2](https://files.ak-ooda.dev/tools/ak-cli-v2)",
  "ak_hash": "sha256:e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
}
```

  * **ak\_hash**: (安全强制) Bridge 会校验下载工具的指纹，防止供应链攻击。

**Response:**

```json
{
  "status": "success",
  "run_id": "bridge-x92ks02",
  "logs": "...",
  "output": "Fixed the bug by updating line 42."
}
```

### 2\. 健康检查 (Health Check)

**GET** `/health?deep=1`

  * 返回 `200 OK`: 桥接正常，且云端凭证有效。
  * 返回 `503 Service Unavailable`: 凭证过期，需要运维介入（重新执行步骤 1）。

-----

## 🛡 安全模型 (Security)

我们遵循 **"Trust, but Verify"** 原则：

  * **Trust**: 信任本地生成的 Auth Token。
  * **Verify**: 强制校验所有输入工具（`ak_hash`）的完整性。
  * **Contain**: 即使开启 YOLO 模式，破坏范围也被物理限制在当前 Namespace 的 Pod 内。

## 🙋 FAQ

**Q: 为什么不直接在 Dockerfile 里 `COPY auth.json`?**
A: **绝对禁止！** 这会导致你的凭证泄露在镜像层中。必须使用 K8s Secret 或类似机制在运行时挂载。

**Q: 除了 Codex，还支持别的吗？**
A: 目前这是 Codex 的参考实现。但 `headless-bridge` 的架构（Secret 挂载 + HTTP 封装）通用适用于 Vercel, Netlify, Terraform Cloud 等任何 CLI 工具。

-----

Created with ❤️ by **AK-OODA** | [Report Issue](https://www.google.com/search?q=https://github.com/yourname/headless-bridge/issues)

```
