# AGENTS.md —— AI 施工守则（企业级分级知识库）

> 任何 AI 编程助手（Hermes / Kimi Code / Claude Code / Codex）在本项目工作前必须完整阅读本文件。
> 配套阅读：docs/01-需求.md（做什么）、docs/02-架构.md（怎么搭）。

## 技术栈（定死，不得擅自更换）

- Python 3.11+ / FastAPI / SQLAlchemy(SQLite) / Chroma / rank_bm25 / pytest
- Embedding: 本机 Ollama bge-m3（http://localhost:11434）
- Chat: DeepSeek API（OpenAI 兼容，base_url 可配置）
- 引入任何新依赖前必须先询问用户

## 硬性红线（违反即返工）

1. **权限过滤必须在检索层执行**（Chroma metadata where 过滤 + BM25 候选集预过滤），禁止"先检索后过滤结果"
2. **解析失败的文档零切片**——脏数据不进库
3. **密钥只走 .env / 环境变量 / app_settings 表**（界面可改时存 DB，接口返回必须打码 `sk-xxx***`）；代码中不得出现任何明文 key
4. **答案必须可溯源**：生成内容必须带引用编号；无依据内容必须拒答
5. **越权尝试必记审计日志**

## 目录规矩

- 业务逻辑只准写在 `services/`；`routers/` 只做接参、鉴权、调 service、回包
- 能力实现（解析/模型/存储）只准写在 `parser/ llm/ storage/`，且必须接口抽象（业务层只依赖接口）
- `models/` 只放 SQLAlchemy 表结构，不放逻辑
- 配置集中在 `core/config.py`（pydantic-settings 读 .env），禁止散落读环境变量
- 运行时数据只写 `data/`（已 gitignore），不得写其他目录

## 编码规范

- 类型标注全覆盖；函数必须有 docstring（做什么/参数/返回）
- 一个功能只留一条实现路径；不留注释掉的死代码
- 命名：模块/函数 snake_case，类 PascalCase，常量 UPPER_SNAKE
- 外部调用（Ollama/DeepSeek）必须带超时与错误处理
- 注释和 docstring 用中文；标识符用英文

## 验证方式（改完代码必须执行）

```bash
cd backend && uv run pytest            # 测试必须全绿
uv run uvicorn app.main:app --port 8000  # 服务能起
curl localhost:8000/health              # 健康检查 200
```

- 权限相关改动：必须跑 `pytest tests/test_permission.py`
- 检索相关改动：必须跑 `pytest tests/test_retrieval.py`
- 只读文档（README/docs/AGENTS.md）修改不需跑测试

## 禁区

- 不许修改 `docker/`、`data/` 下任何文件
- 不许降低权限校验强度来"让测试通过"
- 不许在未询问用户的情况下调用付费 API（DeepSeek 之外的）
