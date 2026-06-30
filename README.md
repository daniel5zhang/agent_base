# 企业 Agent 工作台

本仓库提交到 `daniel5zhang/agent_base.git`，当前按前后端分层管理：

```text
.
├── src/                 # 前端源码，Next.js + assistant-ui
├── src/app/api/chat/    # 前端到后端 Agent SSE 的 Next.js Bridge
├── src/features/        # 工作台外壳与业务面板
├── backend/             # 后端源码，Python FastAPI Agent Runtime
└── docs/                # 架构、参考项目分析、详细设计文档
```

## 前端

技术栈：

- Next.js
- React
- assistant-ui
- Vercel AI SDK
- shadcn/ui
- Base UI
- Tailwind CSS

开发启动：

```bash
npm install
npm run dev
```

默认访问：

```text
http://127.0.0.1:3001
```

## 后端

技术栈：

- Python
- FastAPI
- SQLAlchemy
- SQLite
- OpenAI-compatible model API

开发启动：

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

环境变量示例：

```text
backend/.env.example
```

## 关键文档

- `docs/full-agent-server-design.md`
- `docs/reference-claude-code-analysis.md`

## 当前阶段

前端以 assistant-ui 为主构建通用 Agent 对话体验。后端以 `claude-code-main` 的 QueryEngine / Tool / Permission / Memory / Plugin 思路为参考，建设 Python FastAPI 版企业 Agent Runtime。
