<div align="center">

![ArtiChat Banner](/org.png)


**面向授权测试场景的本地账号注册与运维工作台**

[![Python](https://img.shields.io/badge/Python-3.10%2B-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-backend-009688?style=flat-square&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![Playwright-compatible](https://img.shields.io/badge/Browser-Patchright-4B32C3?style=flat-square)](https://github.com/Kaliiiiiiii-Vinyzu/patchright)
[![Edition](https://img.shields.io/badge/edition-sanitized%20public-16A34A?style=flat-square)](#开源与使用边界)

[中文](README.md) · [English](README.en.md)

</div>

> 一款用于自动化注册 ChatGPT 账号并且获取 Session Token/Access Token/Session Json的服务。

## 项目简介

OrgRegister 是一个运行在本机的账号注册与运维面板，用于在获得明确授权的测试环境中统一管理任务、邮箱验证码、代理、账号健康状态和本地数据。

它把重复的浏览器操作、邮件轮询和任务记录集中到一个轻量的 FastAPI + SQLite 应用中，适合开发调试、流程验证、QA 回归和内部自动化实验。

## 功能概览

- **任务工作台**：创建任务、查看实时进度、保留任务记录，并支持一键清空历史记录。
- **成功号池**：按卡片查看账号状态、注册时间和详细字段；支持展开查看分层信息与删除账号。
- **邮箱验证码**：通过 Graph/IMAP 邮件适配层轮询验证码，不把邮箱内容写入公开仓库。
- **浏览器流程**：基于 Patchright 启动 Chromium，支持代理、超时和人工验证码处理。
- **运行观测**：展示服务状态、浏览器环境、指纹信息和任务日志，便于定位失败原因。

## 界面预览

![ArtiChat Banner](/1.png)

## 快速开始

### 环境要求

| 依赖 | 版本 |
| --- | --- |
| Python | 3.10 或更高版本 |
| Chromium | 由 Patchright 安装 |
| 操作系统 | Windows、macOS 或 Linux |

### 安装与启动

```powershell
cd C:\path\to\Reg-pub
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
patchright install chromium
python run.py
```

打开 <http://127.0.0.1:8001>。

Linux/macOS 激活虚拟环境时使用：

```bash
source .venv/bin/activate
```

### 邮箱池配置

复制示例文件并在本地填写自己的测试凭据：

```powershell
Copy-Item data\emails.example.txt data\emails.txt
```

每行使用 6 个字段，以四个连字符分隔：

```text
MS_EMAIL----MS_PASSWORD----MS_UUID----MSA_REFRESH_TOKEN----TEMP_EMAIL----TEMP_PASSWORD
```

`data/emails.txt` 已加入 `.gitignore`。不要把真实凭据提交到 Git、Issue、截图、日志或聊天记录中。

## 配置位置

基础配置集中在 [`backend/config.py`](backend/config.py)：

| 配置 | 默认值 | 说明 |
| --- | --- | --- |
| `HOST` | `127.0.0.1` | 仅监听本机，适合本地面板 |
| `PORT` | `8001` | Web 服务端口 |
| `DEFAULT_PROXY` | `127.0.0.1:7890` | 默认 HTTP 代理地址 |
| `MAX_CONCURRENT` | `2` | 默认并发任务数 |
| `REGISTER_TIMEOUT` | `300` | 单任务超时时间（秒） |
| `CAPTCHA_TIMEOUT` | `600` | 人工验证码等待时间（秒） |

生产或多人使用前，请自行增加认证、TLS、访问控制和审计策略；默认配置只适合受控的本机环境。

## 项目结构

```text
Reg-pub/
├─ backend/              # FastAPI 服务、注册流程、邮件与代理适配器
├─ frontend/             # 单页面板、国际化、样式和管理操作
├─ data/
│  ├─ emails.example.txt # 脱敏凭据格式示例
│  └─ .gitkeep
├─ tests/                # 单元测试
├─ run.py                # 启动入口
├─ requirements.txt
└─ README*.md
```

## 验证

```powershell
python -m unittest discover -s tests -q
python -m compileall -q backend run.py tests
node --check frontend/manage-actions.js
```


## 开源与使用边界

[Orgnol系列] 本项目仅作为测试与逆向研究，请勿用于非法用途。By Minier Buper

