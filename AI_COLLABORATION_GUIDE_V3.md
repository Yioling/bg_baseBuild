# 薪火项目 — CodeBuddy ↔ 其他 AI 协作指令手册（V3 修订版）

> **用途**：CodeBuddy 作为项目审查者/协调者，将发现的具体问题转化为精确指令，交给其他 AI 执行修复。
> **V3 修订说明**：V2 在 I-03、I-05、I-08 上存在事实性错误（详见 `AI_COLLABORATION_GUIDE_V2_CRITIQUE.md`）。V3 逐条对照 2026-08-05 源码快照重新核验，废止 V2 的错误内容。
> **V3 新增机制**：每条指令附"执行前验证"命令——**先跑验证，结果与指令描述不符则立即停止并反馈 CodeBuddy，不得自行发挥**。
> **最后更新**：2026-08-05（源码快照日期同日）

---

## V2 → V3 修订摘要

| 编号 | V2 结论 | V3 结论 | 变更说明 |
|:---:|:---:|------|------|
| I-01 | 保留 | **保留，修正机理描述** | 真实表现是 NameError→500，不是"返回 success=True" |
| I-02 | 保留 | **保留原样** | 行号复核准确 |
| I-03 | 重写 | **再次重写** | V2 指控 `notify_quiz_submitted` 不存在——错误，它真实存在（notifications.py:150-163）；V2 漏掉真正根因：`modules.notification` 假 import；`_notify` 是死代码应删除 |
| I-04 | 保留 | **保留，补充脆弱点** | email 字段多余 + pending 状态前置依赖 |
| I-05 | 保留 | **保留，替换错误论据** | db.py 全文无任何 FOREIGN KEY 子句，PRAGMA 去留无害；保留它的真实理由是防御一致性 |
| I-06 | 保留 | **保留，简化验证** | 用非绑定调用避免实例化 SelfPurifier |
| I-07 | 保留 | **保留，修正验证声明** | test_admin_back.py 的覆盖关系未证实，改为直接函数级验证 |
| I-08 | 保留 | **修正修复方案** | `except Exception` 不会吞 KeyboardInterrupt（它是 BaseException）；显式 4 类异常反而更脆弱；正确方案是 `except Exception` + logging |
| 附录 B 第 7 条 | 反例错误 | **重写** | 反例 `notify_quiz_submitted` 真实存在；改为"先验证后执行"机制 |

---

## I-01 [P0] auth.py：注册异常路径 NameError + 永不执行的第二个 except

### 问题描述（V3 修正机理）
`backend/auth.py` 第 84-90 行存在两个连续的 `except Exception as e:` 块。真实故障链：

1. 典型异常（INSERT UNIQUE 冲突）发生在第 57-64 行，即第 66 行 `uid = cur.lastrowid` **之前**；
2. 进入第一个 except（第 84-86 行），其返回体引用未绑定的 `uid` → 抛出 `NameError`；
3. `NameError` 在 except 处理体内抛出，**不会被第二个 except 捕获**（同一 try 的 except 不捕获兄弟 except 内的异常）→ 向上传播，FastAPI 返回 500；
4. 结果：用户名冲突时用户看到的是 500 错误，**永远走不到**第 87-90 行的"用户名已存在"友好提示。第二个 except 因此成为事实死代码。

（V2 描述为"异常时返回 success=True"不准确——该返回体根本执行不完。）

### 文件路径
`D:/团队赛/backend/auth.py`（第 84-90 行，已核对）

### 执行前验证
```bash
cd D:/团队赛 && python -c "
import inspect, backend.auth as a
src = inspect.getsource(a.register)
print('双except存在:', src.count('except Exception as e:') == 2)
"
```
预期输出 `True`。若为 `False`，说明已被修复，停止并反馈。

### 修复指令（给 AI）
```
请在 D:/团队赛/backend/auth.py 中定位 register() 函数（约第 49-90 行）。

【授权】auth.py 是 P1 独占文件，本指令已获 P1 授权；其余角色接到本指令须转交 P1。

1. 删除第 84-86 行的第一个 except 块（整块三行：except 行 + 两行 return）。
2. 保留第 87-90 行的第二个 except 块（UNIQUE 冲突 → "用户名已存在"；其他 → str(e)）。
3. 不要触动第 69-80 行的 notify 调用块（那是 I-03 的范围）。

修改后结构：try 正常路径返回 success=True；唯一一个 except 负责失败返回 success=False。
```

### 执行后验证
```bash
cd D:/团队赛 && python -c "
from backend.db import init_db, get_conn
init_db()
from backend.auth import register
conn = get_conn()
conn.execute('DELETE FROM users WHERE username=?', ('test_bug_i01',))
conn.commit(); conn.close()
print(register('test_bug_i01', '123', 'master'))
print(register('test_bug_i01', '123', 'master'))
"
```
预期：第一次 `success=True`；第二次 `success=False, message='用户名已存在'`（V3 修正后第二次不再 500/NameError）。

---

## I-02 [P0] main.py：重复 return 死代码

### 问题描述
`backend/main.py` 第 1026 与第 1028 行，`api_purification_stats` 有两个连续的 `return get_purification_stats()`，第二个永不执行。（行号已核对：函数体第 1021-1028 行。）

### 执行前验证
```bash
cd D:/团队赛 && python -c "
src = open('backend/main.py', encoding='utf-8').read()
print('重复return存在:', src.count('return get_purification_stats()') == 2)
"
```

### 修复指令（给 AI）
```
请在 D:/团队赛/backend/main.py 找到 api_purification_stats（约第 1021-1028 行）。

【授权】main.py 是 P1 独占文件，本指令已获 P1 授权。

删除第 1028 行的 return 语句及其前的空行，保留第 1026 行。
不要触动相邻的 api_purification_report（第 1014-1018 行）。
```

### 执行后验证
```bash
cd D:/团队赛 && python -m pytest tests/test_smoke.py -q
```

---

## I-03 [P0] 通知链路：`modules.notification` 假 import 导致通知静默失效（V3 再次重写）

### 问题描述（V3 重述，废止 V2 版本）
V2 称"`notify_quiz_submitted` 不存在、V1 凭空捏造"——**错误**。该函数真实存在于 `backend/notifications.py` 第 150-163 行，签名：
```python
notify_quiz_submitted(master_id: int, apprentice_name: str, conn=None, company_id: int = 1) -> dict
```
P7 模块共提供三个语义封装：`notify_register_pending`（124-147）、`notify_quiz_submitted`（150-163）、`notify_anomaly`（166-205），另有底层 `notify(user_id, ntype, content, ref_id=None, company_id=1, conn=None)`（72-119）。

**真正的根因（V1/V2 均未指出）**：调用方的 import 路径是假的——

1. `auth.py` 第 10 行：`from modules.notification import notify` —— `modules.notification` **这个包不存在**（真实路径 `backend.notifications`），第 11-14 行的 `except ImportError` **永远命中**，占位函数永远生效，注册通知从未真正发出。
2. `main.py` 第 43 行：同样的假 import + 占位（第 42-46 行），提交检测通知同样从未真正发出。
3. 占位函数接受 `*args, **kwargs`，所以第 72-77 行（auth.py）和第 620-625 行（main.py）传入的 `recipient_role`/`related_id` 错误参数**不会报错**——故障被完全隐藏。
4. `main.py` 第 879-881 行的 `_notify` 定义后**全文零调用**（已检索确认），是死代码。

即：当前系统所有"通知"都被静默吞掉，这不是参数不匹配问题，是**整条链路从未接通**。

### 执行前验证
```bash
cd D:/团队赛 && python -c "
import backend.notifications as n
fns = [f for f in dir(n) if f.startswith('notify')]
print('P7 实际导出:', fns)
assert 'notify_quiz_submitted' in fns, '源码已变化，停止执行并反馈 CodeBuddy'
import pathlib
for f in ['backend/auth.py', 'backend/main.py']:
    src = pathlib.Path(f).read_text(encoding='utf-8')
    print(f, '假import存在:', 'modules.notification' in src)
"
```
预期：P7 导出含 `notify_quiz_submitted`；两文件假 import 均为 `True`。任一不符，停止并反馈。

### 修复指令（给 AI）
```
【授权】auth.py/main.py 属 P1，notifications.py 属 P7（本指令只读 P7 文件，不改）。
本指令已获 P1 授权。

基准：以 backend/notifications.py 当前实现为准。执行前先跑"执行前验证"脚本。

==== 步骤 1：修复 auth.py ====
a. 删除第 8-14 行的假 import 块（try: from modules.notification ... except ... 占位函数）。
b. 替换为真实 import：
    from backend.notifications import notify_register_pending
c. 将 register() 内第 69-80 行的 notify 调用块改为：
    # ===== 注册待审通知：通知本公司全部已批准管理员 =====
    try:
        admins = conn.execute(
            "SELECT id FROM users WHERE role='admin' AND company_id=? AND status='approved'",
            (company_id or 1,)
        ).fetchall()
        admin_ids = [a["id"] for a in admins]
        if admin_ids:
            notify_register_pending(admin_ids, username=username, conn=conn,
                                    company_id=company_id or 1)
    except Exception as e:
        print(f"注册通知发送异常（不影响主流程）: {e}")
   注意：保留外层 try/except——通知失败不得影响注册主流程。

==== 步骤 2：修复 main.py ====
a. 删除第 42-46 行的假 import 块。
b. 将第 618-627 行的提交通知块改为调用 P7 语义封装（不要手写底层 notify）：
    # ===== 提交检测通知师傅 =====
    try:
        from backend.notifications import notify_quiz_submitted
        master_id = user.get("master_id")
        if master_id:
            notify_quiz_submitted(
                master_id,
                apprentice_name=user.get("username") or str(user["user_id"]),
                conn=conn,
                company_id=user.get("company_id") or 1,
            )
    except Exception as e:
        print(f"提交检测通知失败: {e}")
   （此处用局部 import，因为 main.py 顶部 import 较多，局部 import 可将 P7 模块故障
    隔离在通知路径内，不影响主应用启动。）

==== 步骤 3：删除 main.py 死代码 ====
删除第 879-881 行的 _notify 定义（全文零调用，与 I-02 同类死代码）。
删除前自行再确认一次：python -c "import pathlib; print(pathlib.Path('backend/main.py').read_text(encoding='utf-8').count('_notify('))"
若结果大于 1（即存在调用点），停止并反馈 CodeBuddy。

==== 步骤 4：不要做的事 ====
- 不要修改 backend/notifications.py（P7 文件，只读）。
- 不要新增任何 notify_* 函数——需要的封装已存在。
```

### 执行后验证
```bash
cd D:/团队赛 && python -c "
from backend.db import init_db, get_conn
init_db()
from backend.auth import register
import uuid
u = 'test_notify_' + uuid.uuid4().hex[:6]
print(register(u, '123', 'master', company_id=1))
conn = get_conn()
rows = conn.execute(\"SELECT type, content FROM notifications WHERE content LIKE ?\", ('%' + u + '%',)).fetchall()
print('通知落库:', rows)
"
```
预期：注册 `success=True`，且 notifications 表中有 `register_pending` 记录（若公司 1 无已批准 admin 则为空——属正常，查 users 表确认）。

再跑冒烟：`python -m pytest tests/test_smoke.py -q`

---

## I-04 [P1] test_smoke.py：断言字段名错误 + 两处脆弱点

### 问题描述
1. 第 35 行 `assert "access_token" in login2.json()`，实际返回字段是 `"token"`（`auth.py` 第 110 行 login 返回、`API_CONTRACT.md` 第 14 行）。
2. （V3 补充）第 25 行 register 请求体含 `email` 字段，`RegisterReq`（schemas.py 第 11-20 行）无此字段。Pydantic 默认忽略多余字段，无害但应删除以免误导。
3. （V3 补充）该测试断言"注册后即登录成功"，但 `login()` 对 `status='pending'` 用户返回失败——测试实际依赖"smoke_test 已被管理员 approve"的环境残留状态。首次在干净库上跑会失败，这不是字段名能解决的。

### 修复指令（给 AI）
```
请在 D:/团队赛/tests/test_smoke.py 中：
1. 第 35 行改为 assert "token" in login2.json()
2. 删除第 25 行的 "email": "smoke@test.com" 一行（RegisterReq 无此字段）
3. 不要改其他断言。

【测试脆弱性说明（不要求本次修复，登记到 TEAM_PLAN.md §5）】
该 smoke 在干净数据库上会因 pending 状态登录失败。长期方案是测试前置调用管理员
approve 接口或直接 SQL 置 status='approved'。本次仅修字段名，保持最小改动。
```

### 执行后验证
```bash
cd D:/团队赛 && python -m pytest tests/test_smoke.py -q
```
若仍在 `test_register_login_smoke` 失败且报"账号正在审核中"，属上述已知脆弱点，非本次修复引入——登记后跳过。

---

## I-05 [P1] db.py：init_db 每次 DROP 全部表（V3 修正论据）

### 问题描述
`backend/db.py` 第 44-52 行每次启动 DROP 31 张表再重建，除 users 表有备份/恢复外，其余表数据全丢。

### V3 论据修正（废止 V2 的错误理由）
V2 称"删除 `PRAGMA foreign_keys=OFF` 会导致 CREATE TABLE 外键报错"——**错误**：`db.py` 全部 30+ 张表的 DDL 中**没有任何 FOREIGN KEY / REFERENCES 子句**（全文已核对），SQLite 的 CREATE TABLE 也不校验被引用表存在性。该 PRAGMA 保留的真实理由是：① 无害；② 与 `get_conn()` 中 `foreign_keys=ON`（第 24 行）形成显式的建表期/运行期语义区分，防御未来有人加外键约束。**结论与 V2 相同（保留），但执行者必须知道真实理由。**

### 执行前验证
```bash
cd D:/团队赛 && python -c "
src = open('backend/db.py', encoding='utf-8').read()
print('DROP循环存在:', 'DROP TABLE IF EXISTS' in src)
print('外键约束数量(应为0):', src.upper().count('FOREIGN KEY') + src.upper().count('REFERENCES'))
"
```

### 修复指令（给 AI）
```
请在 D:/团队赛/backend/db.py 修改 init_db()。

【授权】db.py 是 P1 独占文件，本指令已获 P1 授权。

==== 步骤 A：幂等化 ====
1. 删除第 41 行 old_users = _backup_old_users(conn)
2. 删除第 44-52 行 DROP TABLE 循环
3. 删除第 73 行 _restore_old_users(conn, old_users)
4. 保留全部 CREATE TABLE IF NOT EXISTS 语句
5. 保留第 30 行 PRAGMA foreign_keys=OFF（无害防御，勿删）
6. _backup_old_users / _restore_old_users 两个函数定义可删除（零调用后成为死代码）

==== 步骤 B：登记 schema 迁移（TEAM_PLAN.md §5 已确认存在，第 41 行）====
在 TEAM_PLAN.md 第 5 节追加：
| P0 | course_questions 表懒建移入 db.py init_db | P1+P6 | P6 当前运行期懒建，需固化为 schema |
| P0 | plans.completed_at 列加入 db.py plans 表 | P1+P6 | 同上 |

==== 步骤 C：显式告知 P6 边界 ====
修复后首次启动，旧库中 plans 表已存在但无 completed_at 列，CREATE TABLE IF NOT EXISTS
不会补列。P6 需在 courses.py 顶部保留 ALTER TABLE 兜底（try/except OperationalError）。
本指令不含此改动，仅告知。
```

### 执行后验证
```bash
cd D:/团队赛 && python -c "
from backend.db import init_db, get_conn
init_db(); print('第一次 OK')
init_db(); print('第二次 OK')
# 数据不丢失验证
conn = get_conn()
conn.execute(\"INSERT INTO company_posts (company_id, author_id, content) VALUES (1, 0, 'i05持久化测试')\")
conn.commit(); conn.close()
init_db()
conn = get_conn()
print('数据保留:', conn.execute(\"SELECT COUNT(*) FROM company_posts WHERE content='i05持久化测试'\").fetchone()[0] == 1)
conn.execute(\"DELETE FROM company_posts WHERE content='i05持久化测试'\"); conn.commit(); conn.close()
"
```
预期：三次 True——幂等 + **数据跨 init 保留**（V2 的验证只测了幂等，没测数据保留）。

---

## I-06 [P2] self_purifier.py：_cosine_sim 实际是 Jaccard

### 问题描述
第 138-143 行 `_cosine_sim` 实现为词集合 Jaccard 交并比；第 119 行 docstring 亦称"余弦相似度"。行号已核对。

### 修复指令（给 AI）
```
【授权】self_purifier.py 是 P2 独占文件，本指令仅下发给 P2。

1. 第 138 行：def _cosine_sim → def _jaccard_sim
2. 第 139 行注释改为："""Jaccard 相似度：词集合交并比（注：非余弦相似度，完整版应换嵌入向量）。"""
3. 第 128 行调用点 self._cosine_sim(...) → self._jaccard_sim(...)
4. 第 119 行 docstring"余弦相似度 > threshold"→"Jaccard 相似度 > threshold"
仅改此文件。
```

### 执行后验证（V3 简化：不实例化，避免连库/加载向量库）
```bash
cd D:/团队赛 && python -c "
from backend.self_purifier import SelfPurifier
v = SelfPurifier._jaccard_sim(None, 'hello world', 'hello there')
print('相似度:', v); assert 0 < v < 1
print('改名 OK')
"
```

---

## I-07 [P2] auth.py：get_company_users N+1 查询

### 问题描述
第 172-190 行对每个徒弟单独查师傅姓名，N+1。行号已核对。

### 修复指令（给 AI）
```
【授权】auth.py 是 P1 独占文件，本指令须由 P1 执行。

将第 172-190 行函数体替换为批量查询版本：

def get_company_users(company_id: int) -> list:
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, username, role, full_name, employee_no, master_id, status, created_at "
        "FROM users WHERE company_id=? ORDER BY role, id",
        (company_id,),
    ).fetchall()

    # 批量获取所有师傅姓名
    master_ids = {r["master_id"] for r in rows if r["role"] == "apprentice" and r["master_id"]}
    master_map = {}
    if master_ids:
        placeholders = ",".join("?" * len(master_ids))
        masters = conn.execute(
            f"SELECT id, full_name, username FROM users WHERE id IN ({placeholders})",
            tuple(master_ids),
        ).fetchall()
        master_map = {m["id"]: (m["full_name"] or m["username"]) for m in masters}

    out = []
    for r in rows:
        d = dict(r)
        d["master_name"] = master_map.get(r["master_id"], "-") if r["role"] == "apprentice" else "-"
        out.append(d)
    return out
```

### 执行后验证（V3 修正：直接函数级验证，不依赖未证实的测试覆盖关系）
```bash
cd D:/团队赛 && python -c "
from backend.db import init_db
init_db()
from backend.auth import get_company_users
users = get_company_users(1)
print('返回条数:', len(users))
print('字段完整:', all('master_name' in u for u in users))
"
```

---

## I-08 [P3] vectorstore.py：持久化鲁棒性（V3 修正方案与论据）

### 问题描述
第 53-71 行 save/load 直接 pickle 读写：写入非原子（中断留半个文件）、加载无兜底（损坏文件直接崩溃）。

### V3 论据修正（废止 V2 的错误理由）
- V2 称"`except Exception` 会吞掉 KeyboardInterrupt/SystemExit"——**错误**：二者继承 `BaseException`，`except Exception` 抓不到它们。
- V2 改用"显式 4 类异常"——**更脆弱**：pickle 反序列化引用已移动/删除的类时抛 `ModuleNotFoundError`/`AttributeError`，不在 4 类之内，损坏文件照样崩溃。
- V2 称"`Path.replace` 在 3.8 以下不可用"——**错误**：3.3 起可用；且本项目用 `int | None` 语法，硬性要求 Python ≥ 3.10。
- 本场景 `except Exception` 是**正确且必要**的：目标是"任何原因加载失败都降级为空库"，反序列化可抛的异常类型无法穷举。配合 logging 保留诊断信息即可。

### 修复指令（给 AI）
```
【授权】vectorstore.py 是 P2 独占文件，本指令须由 P2 执行。

==== save()（第 53-58 行）：原子写入 ====
def save(self, path):
    import os
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    self.path = path
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "wb") as f:
        pickle.dump({"docs": self.docs, "matrix": self.matrix}, f)
    os.replace(str(tmp), str(path))  # 原子替换

==== load()（第 60-71 行）：宽捕获 + 日志降级 ====
@classmethod
def load(cls, path):
    import logging
    p = Path(path)
    store = cls()
    if p.exists():
        try:
            with open(p, "rb") as f:
                data = pickle.load(f)
            store.docs = data.get("docs", [])
            store.matrix = data.get("matrix")
            store._normalize()
            store.path = p
        except Exception as exc:
            # 反序列化可抛异常类型无法穷举（格式错/截断/类移动/版本不兼容），
            # 目标是"任何失败都降级为空库不崩溃"。KeyboardInterrupt/SystemExit
            # 继承 BaseException，不会被本句捕获。
            logging.getLogger(__name__).warning("向量库加载失败，降级为空库: %s", exc)
            store.docs = []
            store.matrix = None
    return store

【安全说明】pickle 反序列化不受信数据有代码执行风险，但本项目向量库文件来自本机
自产，比赛场景可接受；不引入 JSON 序列化（numpy 矩阵序列化成本高，超范围）。
```

### 执行后验证
```bash
cd D:/团队赛 && python -c "
from backend.vectorstore import VectorStore
s = VectorStore(); s.save('backend/data/vs_test.pkl')
s2 = VectorStore.load('backend/data/vs_test.pkl')
print('正常加载 OK, count =', s2.count)
with open('backend/data/vs_corrupt.pkl', 'wb') as f:
    f.write(b'not a pickle')
s3 = VectorStore.load('backend/data/vs_corrupt.pkl')
print('损坏文件降级 OK, count =', s3.count); assert s3.count == 0
import os; os.remove('backend/data/vs_test.pkl'); os.remove('backend/data/vs_corrupt.pkl')
"
```

---

## 附录 A：团队角色红线速查（V3 统一路径风格）

| 角色 | 可写文件 | 禁止触碰 |
|:---:|------|------|
| **P1** | `backend/main.py` `backend/db.py` `backend/auth.py` `backend/schemas.py` `backend/config.py` `run.py` `run_exe.py` `tests/` | — |
| **P2** | `backend/llm.py` `backend/embeddings.py` `backend/vectorstore.py` `backend/self_purifier.py` | P1 枢纽文件 |
| **P3** | `backend/agents/refiner.py` `assessor.py` `planner.py` `tutor.py` `reviewer.py` | P1 枢纽文件 |
| **P4** | `backend/ingest.py` `backend/pdf_gen.py` `backend/data/sample_kb/` | P1 枢纽文件 |
| **P5** | `desktop_app.py` `ui/` | P1 枢纽文件 |
| **P6** | `backend/courses.py` `backend/progress_view.py` `backend/quiz.py` `backend/admin_back.py` | P1 枢纽文件 |
| **P7** | `backend/notifications.py` `backend/account_security.py` `backend/social.py` | P1 枢纽文件 |

> 跨角色文件需双方显式授权。下指令前先核对文件归属。

---

## 附录 B：给 AI 的通用纪律（V3 修订）

```
遵守以下铁律：
1. 只修改指令中明确允许的文件。涉及 P1 枢纽文件（main.py/db.py/auth.py/schemas.py/config.py）
   时，确认指令头部有"P1 已授权"字样，否则停止并反馈。
2. 【执行前验证优先】每条指令附带的"执行前验证"脚本必须先跑。结果与指令描述不符
  （函数不存在/行号漂移/特征码缺失），立即停止并向 CodeBuddy 反馈验证输出，
   不得自行猜测修复，更不得"创造"指令中提到的函数。
3. 用精准替换，不整体重写；替换前后保留至少 2 行上下文。
4. 函数返回 {success: bool, ...}，字段名对齐 API_CONTRACT.md。
5. import 路径：项目根是 D:/团队赛/，用 from backend.xxx import yyy。
   【特别注意】modules.xxx 是历史遗留假路径，见到即为 Bug，不要模仿。
6. 中文注释和字符串优先。
7. 改动后跑 python -m pytest tests/test_smoke.py -q 确认冒烟。
8. 引用 Python 异常/标准库行为作为论据时，必须先在解释器里验证
  （如 except Exception 能否捕获 KeyboardInterrupt，一行代码即可验证）。
```

---

## 附录 C：V2 → V3 修订日志

| 条目 | V2 错误 | V3 修订 |
|------|------|------|
| I-03 | 指控 `notify_quiz_submitted` 不存在（实际存在于 notifications.py:150-163） | 恢复使用 P7 语义封装；废止手写底层调用方案 |
| I-03 | 漏掉根因 `modules.notification` 假 import；误诊"顶部 import 会致启动失败" | 指出假 import 导致通知链路从未接通；占位函数吞掉参数错误 |
| I-03 | `_notify` 定性为"平行实现，保留" | 更正为死代码（零调用），删除 |
| I-01 | 机理误述为"返回 success=True" | 更正为 NameError→500，友好提示永不可达 |
| I-04 | 只修字段名 | 补充 email 多余字段 + pending 前置依赖脆弱点 |
| I-05 | 虚构"外键约束报错"论据 | 更正：全文无 FOREIGN KEY 子句；保留 PRAGMA 的真实理由是防御一致性 |
| I-07 | 验证依赖未证实的测试覆盖 | 改为直接函数级验证 |
| I-08 | "Exception 吞 KeyboardInterrupt"错误论据；4 类显式异常更脆弱；"Path.replace 3.8 以下不可用"错误 | 改为 `except Exception` + logging；删除全部错误论据 |
| 附录 B | 反幻觉条款引用真实存在的函数作反例 | 改为"执行前验证"机制（第 2 条）；新增"技术论据先验证"（第 8 条） |

---

*本文件由 CodeBuddy 对照 2026-08-05 源码快照逐条核验后修订。V1、V2 同时废止，以本文件为准。*
