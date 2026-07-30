# 薪火 · 师傅带徒 AI 导师系统

> **ISBG 2026 TS-Force AI 创新大赛（预选赛）参赛作品**

## 📖 选题背景

在软件企业中，"师傅带徒弟"是最常见也是最高效的新人培养方式。然而传统模式存在诸多痛点：
- 师傅精力有限，难以一对一持续关注每个徒弟的成长
- 新人学习缺乏系统性，知识碎片化
- 学习效果无法量化评估，师傅难以针对性调整培养方案
- 不同项目/岗位的知识传承依赖口口相传，容易流失

**薪火系统**以 AI 多智能体技术解决上述问题，实现知识传承的自动化、个性化和可量化。

## 🚀 功能介绍

### 师傅端
| 功能 | 描述 |
|------|------|
| 投喂资料 | 支持本地文件夹（md/txt/pdf/docx/代码）和博客URL自动抓取 |
| AI精炼 | Refiner智能体自动从资料中抽取知识维度和考点树 |
| 徒弟管理 | 创建/管理徒弟账号，同门组隔离 |
| 学习计划 | Planner智能体根据摸底结果生成个性化日历计划，师傅可修改 |
| 学情看板 | 查看每个徒弟的掌握等级趋势、考试评分、错题分布 |

### 徒弟端
| 功能 | 描述 |
|------|------|
| 摸底考试 | Assessor智能体分层出题（易→中→难），AI批改+定级 |
| 每日学习 | 按日历计划获取当日PDF讲义，AI陪练答疑 |
| 当日复习 | Reviewer智能体根据当日内容生成随堂小测 |
| 错题本 | 永久记录所有考试/复习中的错题与解析 |
| 同门战况 | 同一师傅门下的徒弟互相可见进度/成绩/错题，竞技激励 |

## 🏗️ 技术架构

```
┌────────────────────────────────────────────┐
│                  前端 SPA                    │
│        原生 HTML/CSS/JS 单页应用             │
│      （花叔Design设计语言 · 高保真UI）        │
└────────────────┬───────────────────────────┘
                 │ REST API
┌────────────────┴───────────────────────────┐
│              FastAPI 后端                    │
│  ┌─────────────────────────────────────┐   │
│  │         AI 多智能体引擎               │   │
│  │  Refiner │ Assessor │ Planner        │   │
│  │  Tutor   │ Reviewer (RAG陪练)        │   │
│  └─────────────────────────────────────┘   │
│  ┌──────────┐ ┌──────────┐ ┌──────────┐   │
│  │  LLM客户端│ │ 本地向量库│ │ PDF生成  │   │
│  │(OpenAI兼容)│ │(余弦检索)│ │(reportlab)│   │
│  └──────────┘ └──────────┘ └──────────┘   │
└────────────────┬───────────────────────────┘
                 │
┌────────────────┴───────────────────────────┐
│              SQLite 数据库                   │
│  users │ kb_documents │ dimensions          │
│  assessments │ study_plans │ reviews        │
└────────────────────────────────────────────┘
```

### 核心依赖
- **后端**：Python 3.10+ / FastAPI / SQLite / openai / fastembed
- **前端**：原生 HTML/CSS/JS（零构建依赖）
- **LLM**：OpenAI兼容协议，默认DeepSeek，可切换通义/Ollama
- **嵌入**：fastembed + jina-embeddings-v2-small-zh（本地中文嵌入）
- **PDF**：reportlab + fpdf2

## 🤖 AI 使用心得

### 1. 多智能体协作
5个专用智能体分工明确，每个智能体有独立的系统提示词和职责边界，避免单一Prompt的上下文过载问题。

### 2. RAG检索增强
本地向量库存储知识资料，徒弟提问时先检索相关知识片段再交由LLM回答，既提升回答准确性，又提供引用来源增加可信度。

### 3. 无Key兜底设计
当未配置API Key时，系统内置演示回答，保证开箱即可演示全流程闭环，降低比赛演示风险。

### 4. JSON解析鲁棒性
LLM输出不可控是常见问题。本系统实现了多层降级JSON解析：去除Markdown围栏 → 精确JSON解析 → 括号匹配截取，大幅提升结构化输出的可靠性。

### 5. 自适应学习
Assessor先摸底评估每位徒弟的知识水平，Planner据此生成"弱项多排、强项少排"的个性化计划，实现因材施教。

## 🎬 演示说明

### 运行步骤
```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置（可选，不配置则使用演示模式）
cp .env.example .env
# 编辑 .env 填入 LLM_API_KEY

# 3. 启动
python run.py

# 4. 打开浏览器访问
http://localhost:8000
```

### 演示流程（≤3分钟）
1. **师傅登录** → demo_master / 123456
2. **投喂资料** → 加载示例知识库（智能订单交易系统）
3. **AI精炼** → 自动生成4个知识维度（业务背景/幂等与事务/高并发/稳定性）
4. **创建徒弟** → 注册一个新徒弟账号
5. **徒弟登录** → 接受摸底考试（AI出题+批改+定级）
6. **生成计划** → 师傅点击生成，AI根据摸底结果安排学习计划
7. **下载PDF** → 徒弟下载当日讲义包
8. **当日复习** → 徒弟完成复习题，AI批改
9. **学情看板** → 师傅查看徒弟的掌握等级和错题分布

### 切换LLM Provider
| 提供商 | LLM_BASE_URL |
|--------|-------------|
| DeepSeek | https://api.deepseek.com/v1 |
| 通义千问 | https://dashscope.aliyuncs.com/compatible-mode/v1 |
| OpenAI | https://api.openai.com/v1 |
| Ollama本地 | http://localhost:11434/v1 |

## 📂 项目结构
```
TSForce_MentorAI/
├── run.py                    # 启动入口
├── requirements.txt          # 依赖
├── .env.example              # 配置模板
├── README.md                 # 本文件
├── demo_script.md            # 演示视频脚本
├── backend/
│   ├── main.py               # FastAPI路由
│   ├── config.py             # 配置
│   ├── db.py                 # 数据库
│   ├── auth.py               # 认证
│   ├── llm.py                # LLM客户端
│   ├── embeddings.py         # 嵌入模型
│   ├── vectorstore.py        # 向量库
│   ├── ingest.py             # 资料摄取
│   ├── schemas.py            # Pydantic模型
│   ├── pdf_gen.py            # PDF生成
│   ├── agents/               # 智能体
│   │   ├── refiner.py        # 精炼Agent
│   │   ├── assessor.py       # 测评Agent
│   │   ├── planner.py        # 计划Agent
│   │   ├── tutor.py          # 陪练Agent
│   │   └── reviewer.py       # 复习Agent
│   └── data/
│       └── sample_kb/        # 示例知识库
└── frontend/
    └── index.html            # SPA单页应用
```

## 👥 团队分工建议
- **模块A**：后端核心（db.py, auth.py, schemas.py, config.py）
- **模块B**：LLM与向量库（llm.py, embeddings.py, vectorstore.py）
- **模块C**：智能体实现（agents目录下5个Agent）
- **模块D**：资料摄取与PDF（ingest.py, pdf_gen.py）
- **模块E**：API路由与前端（main.py, index.html）
