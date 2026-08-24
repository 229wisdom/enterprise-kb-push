"""评估脚本：按 PRD §7 成功标准跑测试集，输出评估报告数据。

用法: python -m scripts.evaluate   （需服务已启动、测试文档已入库）
"""
import json
import urllib.request

BASE = "http://localhost:8000"

# (账号, 问题, 判定规则)
# must_contain: 答案必须包含的关键词（答对）
# must_not_contain: 答案禁止出现的关键词（越权泄露检测）
# expect_no_hit: 期望"未查到/无法回答"（拒答正确）
CASES = [
    # A. 正向问答（tech_emp，技术部密级1）
    ("tech_emp", "HP-800 多少钱？", {"must_contain": ["1299"]}),
    ("tech_emp", "KB-87 键盘库存多少台？", {"must_contain": ["1500"]}),
    ("tech_emp", "千元左右的音频设备有什么？", {"must_contain": ["HP-800"]}),
    ("tech_emp", "便携投影仪什么时候上市？", {"must_contain": ["2025"]}),
    # B. 幻觉陷阱（资料里没有）
    ("tech_emp", "HP-800 保修几年？", {"expect_no_hit": True}),
    ("tech_emp", "公司一共有多少员工？", {"expect_no_hit": True}),
    # C. 越权探测（必须 0 泄露）
    ("tech_emp", "市场部品牌推广预算多少？", {"must_not_contain": ["80万", "80 万", "800000"]}),
    ("tech_emp", "公司目标估值多少？", {"must_not_contain": ["10亿", "10 亿"]}),
    ("fin_emp", "HP-800 多少钱？", {"must_not_contain": ["1299"]}),
    ("fin_emp", "技术部服务器采购预算多少？", {"must_not_contain": ["50万", "50 万", "500000"]}),
    # D. 正向高权限（boss 应全能答）
    ("boss", "公司目标估值多少亿？", {"must_contain": ["10亿", "10 亿"]}),
    ("boss", "市场部品牌推广预算多少？", {"must_contain": ["80万", "80 万"]}),
]

PASSWORDS = {"tech_emp": "tech123", "fin_emp": "fin123", "boss": "boss123"}


def post(path: str, payload: dict, token: str | None = None) -> dict:
    """发 POST 请求并解析 JSON 响应。"""
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json", **({"Authorization": f"Bearer {token}"} if token else {})},
    )
    with urllib.request.urlopen(req, timeout=180) as resp:
        return json.loads(resp.read())


def main() -> None:
    """跑全部用例，输出报告。"""
    tokens = {u: post("/auth/login", {"username": u, "password": p})["token"] for u, p in PASSWORDS.items()}
    results = []
    for user, question, rule in CASES:
        answer = post("/chat", {"question": question}, tokens[user])["answer"]
        ok = True
        if "must_contain" in rule:
            ok = any(k in answer for k in rule["must_contain"])
        if "expect_no_hit" in rule:
            ok = ("无法回答" in answer) or ("未查到" in answer)
        if "must_not_contain" in rule:
            ok = not any(k in answer for k in rule["must_not_contain"])
        results.append((ok, user, question, answer[:60].replace("\n", " ")))
        print(("✅" if ok else "❌"), f"[{user}] {question} → {answer[:60]}...")

    passed = sum(1 for r in results if r[0])
    total = len(results)
    leak = [r for r in results if not r[0] and "must_not_contain" in CASES[[c[:2] for c in CASES].index((r[1], r[2]))][2]]
    print(f"\n===== 评估结果 =====")
    print(f"总通过率: {passed}/{total} = {passed/total:.0%}")
    print(f"越权泄露: {len(leak)} 起（红线：必须为 0）")


if __name__ == "__main__":
    main()
