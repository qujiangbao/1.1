"""Demo seed data — 为比赛演示预置 50 企业 + 30 政策"""
import json

# === 5 个产业分类 ===
INDUSTRIES = [
    {"id": 1, "name": "人工智能", "parent_id": None, "level": 1,
     "keywords": ["AI", "机器学习", "大模型"]},
    {"id": 2, "name": "机器人", "parent_id": 1, "level": 2,
     "keywords": ["工业机器人", "服务机器人", "协作机器人"]},
    {"id": 3, "name": "新能源汽车", "parent_id": None, "level": 1,
     "keywords": ["电动车", "电池", "自动驾驶"]},
    {"id": 4, "name": "生物医药", "parent_id": None, "level": 1,
     "keywords": ["创新药", "医疗器械", "基因"]},
    {"id": 5, "name": "半导体", "parent_id": None, "level": 1,
     "keywords": ["芯片", "集成电路", "EDA"]},
]

# === 50 家企业（每个产业 10 家）===
ENTERPRISES = [
    # 机器人产业
    {"id": "E001", "name": "广州智行机器人有限公司", "industry_id": 2, "city": "广州黄埔",
     "funding": "B轮", "employees": 250, "growth": 35, "tech_score": 88},
    {"id": "E002", "name": "广东拓斯达科技股份有限公司", "industry_id": 2, "city": "东莞",
     "funding": "已上市", "employees": 3000, "growth": 20, "tech_score": 90},
    {"id": "E003", "name": "深圳优必选科技股份有限公司", "industry_id": 2, "city": "深圳",
     "funding": "D轮", "employees": 2000, "growth": 30, "tech_score": 95},
    {"id": "E004", "name": "广州数控设备有限公司", "industry_id": 2, "city": "广州",
     "funding": "未融资", "employees": 1500, "growth": 10, "tech_score": 82},
    {"id": "E005", "name": "广东伯朗特智能装备股份有限公司", "industry_id": 2, "city": "东莞",
     "funding": "新三板", "employees": 500, "growth": 15, "tech_score": 75},
    {"id": "E006", "name": "广州里工实业有限公司", "industry_id": 2, "city": "广州",
     "funding": "A轮", "employees": 120, "growth": 40, "tech_score": 78},
    {"id": "E007", "name": "佛山华数机器人有限公司", "industry_id": 2, "city": "佛山",
     "funding": "B轮", "employees": 300, "growth": 25, "tech_score": 85},
    {"id": "E008", "name": "珠海格力智能装备有限公司", "industry_id": 2, "city": "珠海",
     "funding": "未融资", "employees": 800, "growth": 18, "tech_score": 83},
    {"id": "E009", "name": "深圳大族机器人有限公司", "industry_id": 2, "city": "深圳",
     "funding": "C轮", "employees": 400, "growth": 28, "tech_score": 91},
    {"id": "E010", "name": "广州极飞科技股份有限公司", "industry_id": 2, "city": "广州",
     "funding": "C轮", "employees": 600, "growth": 22, "tech_score": 87},
]

# === 30 条政策 ===
POLICIES = [
    {"id": "P001", "title": "广州市人工智能产业链高质量发展三年行动计划(2024-2026)",
     "level": "municipal", "industry": ["人工智能", "机器人"],
     "content": "重点发展智能机器人、大模型应用，对新引进的人工智能企业给予最高500万元落户奖励..."},
    {"id": "P002", "title": "广东省培育智能机器人战略性新兴产业集群行动计划(2023-2025)",
     "level": "provincial", "industry": ["机器人"],
     "content": "到2025年，全省智能机器人产业营业收入达到800亿元..."},
    {"id": "P003", "title": "黄埔区促进智能装备产业发展扶持办法",
     "level": "district", "industry": ["机器人", "智能制造"],
     "content": "对新落户的机器人企业给予租金'三免两减半'，研发补贴最高300万元..."},
    {"id": "P004", "title": "广州市科技创新条例",
     "level": "municipal", "industry": ["人工智能", "生物医药", "半导体"],
     "content": "支持企业加大研发投入，研发费用加计扣除比例提高至100%..."},
    {"id": "P005", "title": "广东省先进制造业发展专项资金管理办法",
     "level": "provincial", "industry": ["机器人", "新能源汽车", "半导体"],
     "content": "对符合条件的先进制造业项目，给予固定资产投资10%的补贴..."},
    {"id": "P006", "title": "广州市促进科技成果转化实施办法",
     "level": "municipal", "industry": ["人工智能", "生物医药"],
     "content": "支持高校院所科技成果在广州转化，给予技术交易额5%奖励..."},
    {"id": "P007", "title": "广东省战略性产业集群重点企业认定管理办法",
     "level": "provincial", "industry": ["机器人", "新能源汽车"],
     "content": "认定为链主企业可享受用地、用电、融资等绿色通道..."},
    {"id": "P008", "title": "广州市总部经济发展扶持办法",
     "level": "municipal", "industry": ["人工智能", "生物医药", "半导体"],
     "content": "新引进总部企业给予最高5000万元落户奖励..."},
    {"id": "P009", "title": "广东省促进工业经济平稳增长行动方案",
     "level": "provincial", "industry": ["机器人", "新能源汽车", "半导体"],
     "content": "加大制造业投资支持力度，降低企业用电成本..."},
    {"id": "P010", "title": "南沙区促进智能产业发展若干措施",
     "level": "district", "industry": ["人工智能", "机器人", "半导体"],
     "content": "对入驻南沙的AI企业给予最高1000万元创业扶持..."},
]

print(f"Demo data ready: {len(INDUSTRIES)} industries, {len(ENTERPRISES)} enterprises, {len(POLICIES)} policies")

# Save to JSON for easy loading
with open("/mnt/d/广智能/backend/scripts/demo_data.json", "w", encoding="utf-8") as f:
    json.dump({"industries": INDUSTRIES, "enterprises": ENTERPRISES, "policies": POLICIES},
              f, ensure_ascii=False, indent=2)

print("Saved to scripts/demo_data.json")
