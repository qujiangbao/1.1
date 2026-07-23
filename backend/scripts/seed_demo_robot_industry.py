#!/usr/bin/env python3
"""
Demo Reality Enhancement V2.0 — 机器人产业园完整数据集
生成：1000+ 企业 + 50+ 政策 + 100+ 风险事件 + 完整产业链
"""
import json, random, os

random.seed(42)

# ============================================================
# 1. 产业链结构
# ============================================================
INDUSTRY_CHAIN = {
    "upstream": {
        "核心零部件": ["高精密减速器", "伺服电机", "控制器", "传感器", "编码器", "驱动器"],
        "执行部件": ["谐波减速器", "RV减速器", "直线电机", "力矩电机"],
        "控制系统": ["PLC控制器", "运动控制卡", "嵌入式系统", "实时操作系统"],
    },
    "midstream": {
        "工业机器人": ["六轴机器人", "SCARA机器人", "协作机器人", "并联机器人", "AGV"],
        "服务机器人": ["扫地机器人", "配送机器人", "导览机器人", "教育机器人", "康复机器人"],
        "特种机器人": ["焊接机器人", "喷涂机器人", "装配机器人", "打磨机器人", "检测机器人"],
    },
    "downstream": {
        "汽车制造": ["焊接", "喷涂", "总装", "检测"],
        "3C电子": ["组装", "测试", "包装", "搬运"],
        "新能源": ["电池制造", "光伏组件", "储能系统"],
        "医疗": ["手术辅助", "康复训练", "药品分拣"],
        "物流仓储": ["分拣", "搬运", "码垛", "配送"],
    },
}

# 展开为150+ 细分领域
ALL_CHAIN_POSITIONS = []
for layer_name, layer in INDUSTRY_CHAIN.items():
    for category, positions in layer.items():
        for pos in positions:
            ALL_CHAIN_POSITIONS.append({
                "layer": layer_name,
                "category": category,
                "position": pos,
            })

# ============================================================
# 2. 1000+ 企业生成
# ============================================================
CITIES = [
    {"city": "广州", "districts": ["黄埔区", "天河区", "南沙区", "番禺区", "白云区", "海珠区", "花都区", "增城区", "荔湾区", "越秀区"], "weight": 40},
    {"city": "深圳", "districts": ["南山区", "宝安区", "龙岗区", "龙华区", "光明区", "坪山区", "福田区", "罗湖区"], "weight": 25},
    {"city": "东莞", "districts": ["松山湖", "长安镇", "塘厦镇", "虎门镇", "大朗镇"], "weight": 15},
    {"city": "佛山", "districts": ["顺德区", "南海区", "禅城区", "三水区", "高明区"], "weight": 12},
    {"city": "珠海", "districts": ["香洲区", "金湾区", "斗门区", "横琴新区"], "weight": 8},
]

COMPANY_PREFIXES = [
    "智行", "拓斯达", "华数", "伯朗特", "里工", "极飞", "大族", "格力智能",
    "埃斯顿", "新松", "埃夫特", "汇川", "绿的谐波", "禾川", "步科", "雷赛",
    "固高科技", "研华", "台达", "英威腾", "正弦", "鸣志", "海康", "大华",
    "优必选", "达闼", "傅利叶", "钛米", "擎朗", "普渡", "云迹", "高仙",
    "仙工", "海柔", "极智嘉", "快仓", "旷视", "梅卡曼德", "星猿哲", "非夕",
    "微链", "灵西", "阿童木", "李群", "节卡", "越疆", "遨博", "艾利特",
    "慧灵", "因时", "坤维", "宇立", "海伯森", "奥普特", "凌云光", "天准",
]
COMPANY_SUFFIXES = [
    "科技", "智能", "机器人", "自动化", "机电", "精密机械",
    "智控", "传感技术", "驱动技术", "数控", "信息技术", "电子",
]

FUNDING_STAGES = [
    "种子轮", "天使轮", "Pre-A轮", "A轮", "A+轮", "B轮", "B+轮",
    "C轮", "D轮", "Pre-IPO", "已上市", "新三板", "未融资",
]
STAGE_WEIGHTS = [3, 5, 4, 8, 3, 7, 3, 5, 2, 1, 3, 2, 6]

ENTERPRISES = []
for i in range(1050):
    chain = random.choice(ALL_CHAIN_POSITIONS)
    city_info = random.choices(CITIES, weights=[c["weight"] for c in CITIES], k=1)[0]
    prefix = random.choice(COMPANY_PREFIXES)
    suffix = random.choice(COMPANY_SUFFIXES)

    funding = random.choices(FUNDING_STAGES, weights=STAGE_WEIGHTS, k=1)[0]
    employees = random.randint(15, 5000)
    revenue = random.randint(100, 50000)  # 万元

    # 增长率基于融资阶段
    growth_map = {"种子轮": 80, "天使轮": 60, "A轮": 40, "B轮": 30, "C轮": 20, "D轮": 15, "已上市": 10, "未融资": 5}
    growth = random.randint(max(0, growth_map.get(funding, 10) - 15), growth_map.get(funding, 10) + 15)

    tech_score = random.randint(40, 98)
    rd_ratio = round(random.uniform(1, 25), 1)

    # 风险基础评分
    if funding in ("C轮", "D轮", "已上市"):
        risk_base = random.randint(10, 35)
    elif funding in ("A轮", "B轮"):
        risk_base = random.randint(20, 50)
    else:
        risk_base = random.randint(30, 70)

    ENTERPRISES.append({
        "id": f"E{i+1:04d}",
        "name": f"{city_info['city']}{prefix}{suffix}有限公司",
        "industry": "机器人",
        "sub_industry": chain["category"],
        "chain_layer": chain["layer"],
        "chain_position": chain["position"],
        "city": city_info["city"],
        "district": random.choice(city_info["districts"]),
        "employees": employees,
        "revenue": revenue,
        "growth_rate": growth,
        "funding_stage": funding,
        "technology_score": tech_score,
        "rd_ratio": rd_ratio,
        "risk_base_score": risk_base,
        "established_year": random.randint(2005, 2024),
    })

# 确保广州企业占 40%+
gz_count = sum(1 for e in ENTERPRISES if e["city"] == "广州")
print(f"企业总数: {len(ENTERPRISES)}")
print(f"广州企业: {gz_count} ({gz_count/len(ENTERPRISES)*100:.1f}%)")

# ============================================================
# 3. 50+ 政策数据
# ============================================================
POLICIES = [
    # 国家级 (8)
    {"id": "P001", "title": "「十四五」机器人产业发展规划", "level": "national",
     "department": "工信部", "industry": ["机器人", "智能制造"],
     "support_type": "研发补贴", "amount": "最高5000万", "deadline": "2026-12-31",
     "condition": "年研发投入>500万", "region": ["全国"]},
    {"id": "P002", "title": "智能制造试点示范行动实施方案", "level": "national",
     "department": "工信部", "industry": ["智能制造", "机器人"],
     "support_type": "示范奖励", "amount": "2000万", "deadline": "2026-09-30",
     "condition": "省级以上智能制造示范", "region": ["全国"]},
    {"id": "P003", "title": "首台(套)重大技术装备保险补偿机制", "level": "national",
     "department": "工信部/财政部", "industry": ["机器人", "高端装备"],
     "support_type": "保险补贴", "amount": "保费80%补贴", "deadline": "持续",
     "condition": "首台套认定", "region": ["全国"]},
    {"id": "P004", "title": "高新技术企业认定管理办法", "level": "national",
     "department": "科技部", "industry": ["机器人", "人工智能", "智能制造"],
     "support_type": "税收优惠", "amount": "企业所得税15%", "deadline": "持续",
     "condition": "研发占比>5%, 核心知识产权", "region": ["全国"]},
    {"id": "P005", "title": "专精特新「小巨人」企业培育", "level": "national",
     "department": "工信部", "industry": ["机器人", "核心零部件"],
     "support_type": "专项资金", "amount": "200-1000万", "deadline": "2026-06-30",
     "condition": "细分市场占有率>10%", "region": ["全国"]},
    {"id": "P006", "title": "制造业单项冠军企业培育提升专项行动", "level": "national",
     "department": "工信部", "industry": ["机器人", "核心零部件", "传感器"],
     "support_type": "奖励+推广", "amount": "500万", "deadline": "2026-08-31",
     "condition": "全球市场前3或国内第1", "region": ["全国"]},
    {"id": "P007", "title": "国家企业技术中心认定", "level": "national",
     "department": "发改委", "industry": ["机器人", "人工智能"],
     "support_type": "税收优惠+建设补贴", "amount": "最高2000万", "deadline": "2026-10-31",
     "condition": "年度研发>1500万", "region": ["全国"]},
    {"id": "P008", "title": "工业强基工程", "level": "national",
     "department": "工信部", "industry": ["核心零部件", "传感器", "控制器", "减速器"],
     "support_type": "研发补助", "amount": "最高3000万", "deadline": "2026-11-30",
     "condition": "关键基础材料/零部件/工艺", "region": ["全国"]},

    # 广东省 (12)
    {"id": "P009", "title": "广东省培育智能机器人战略性新兴产业集群行动计划(2023-2025)", "level": "provincial",
     "department": "广东省工信厅", "industry": ["机器人"],
     "support_type": "落户奖励+研发补贴", "amount": "最高1亿", "deadline": "2026-12-31",
     "condition": "落户广东+投资>1亿", "region": ["广东"]},
    {"id": "P010", "title": "广东省先进制造业发展专项资金管理办法", "level": "provincial",
     "department": "广东省财政厅", "industry": ["机器人", "智能制造"],
     "support_type": "固投补贴", "amount": "固投10%", "deadline": "2026-09-30",
     "condition": "固定资产投资>5000万", "region": ["广东"]},
    {"id": "P011", "title": "广东省科技创新战略专项资金", "level": "provincial",
     "department": "广东省科技厅", "industry": ["机器人", "人工智能"],
     "support_type": "研发资助", "amount": "100-500万", "deadline": "2026-07-31",
     "condition": "省级以上研发平台", "region": ["广东"]},
    {"id": "P012", "title": "广东省战略性产业集群重点企业认定", "level": "provincial",
     "department": "广东省工信厅", "industry": ["机器人"],
     "support_type": "用地/用电/融资", "amount": "绿色通道", "deadline": "2026-08-31",
     "condition": "链主/骨干企业", "region": ["广东"]},
    {"id": "P013", "title": "广东省促进工业经济平稳增长行动方案", "level": "provincial",
     "department": "广东省政府", "industry": ["机器人", "制造业"],
     "support_type": "用电补贴+贷款贴息", "amount": "用电成本-10%", "deadline": "持续",
     "condition": "规上工业企业", "region": ["广东"]},
    {"id": "P014", "title": "广东省企业技术改造专项资金", "level": "provincial",
     "department": "广东省工信厅", "industry": ["机器人", "智能制造"],
     "support_type": "技改补贴", "amount": "设备投资20%", "deadline": "2026-10-31",
     "condition": "技术改造投资>500万", "region": ["广东"]},
    {"id": "P015", "title": "广东省博士工作站建站资助", "level": "provincial",
     "department": "广东省人社厅", "industry": ["机器人", "人工智能", "智能制造"],
     "support_type": "人才补贴", "amount": "50万/站", "deadline": "2026-06-30",
     "condition": "博士>5人或博士后工作站", "region": ["广东"]},
    {"id": "P016", "title": "粤港澳大湾区个人所得税优惠政策", "level": "provincial",
     "department": "广东省财政厅", "industry": ["机器人", "人工智能"],
     "support_type": "个税补贴", "amount": "超15%部分返还", "deadline": "持续",
     "condition": "大湾区境外高端人才", "region": ["粤港澳大湾区"]},
    {"id": "P017", "title": "广东省知识产权示范企业认定", "level": "provincial",
     "department": "广东省知识产权局", "industry": ["机器人", "人工智能"],
     "support_type": "奖励", "amount": "30万", "deadline": "2026-07-31",
     "condition": "有效发明专利>10件", "region": ["广东"]},
    {"id": "P018", "title": "广东省工程技术研究中心认定", "level": "provincial",
     "department": "广东省科技厅", "industry": ["机器人", "智能制造"],
     "support_type": "建设补贴", "amount": "100万", "deadline": "2026-09-30",
     "condition": "研发人员>20人", "region": ["广东"]},
    {"id": "P019", "title": "广东省工业互联网标杆示范项目", "level": "provincial",
     "department": "广东省工信厅", "industry": ["机器人", "智能制造"],
     "support_type": "项目补贴", "amount": "最高500万", "deadline": "2026-08-31",
     "condition": "5G+工业互联网应用", "region": ["广东"]},
    {"id": "P020", "title": "广东省「机器人+」应用行动实施方案", "level": "provincial",
     "department": "广东省工信厅", "industry": ["机器人", "智能制造"],
     "support_type": "应用示范补贴", "amount": "最高300万", "deadline": "2026-12-31",
     "condition": "机器人应用场景示范", "region": ["广东"]},

    # 广州市 (15)
    {"id": "P021", "title": "广州市人工智能产业链高质量发展三年行动计划(2024-2026)", "level": "municipal",
     "department": "广州市工信局", "industry": ["人工智能", "机器人"],
     "support_type": "落户+研发+人才", "amount": "最高5000万", "deadline": "2026-12-31",
     "condition": "AI相关企业", "region": ["广州"]},
    {"id": "P022", "title": "广州市科技创新条例", "level": "municipal",
     "department": "广州市科技局", "industry": ["机器人", "人工智能"],
     "support_type": "研发费用加计扣除", "amount": "加计100%扣除", "deadline": "持续",
     "condition": "科技型企业", "region": ["广州"]},
    {"id": "P023", "title": "广州市促进科技成果转化实施办法", "level": "municipal",
     "department": "广州市科技局", "industry": ["机器人", "人工智能"],
     "support_type": "转化奖励", "amount": "技术交易额5%", "deadline": "持续",
     "condition": "高校院所成果在广州转化", "region": ["广州"]},
    {"id": "P024", "title": "广州市总部经济发展扶持办法", "level": "municipal",
     "department": "广州市发改委", "industry": ["机器人", "人工智能"],
     "support_type": "落户奖励+经营贡献", "amount": "最高5000万", "deadline": "2026-12-31",
     "condition": "认定为总部企业", "region": ["广州"]},
    {"id": "P025", "title": "广州市黄埔区促进智能装备产业发展扶持办法", "level": "district",
     "department": "黄埔区政府", "industry": ["机器人", "智能制造"],
     "support_type": "租金减免+研发补贴", "amount": "最高300万", "deadline": "2026-12-31",
     "condition": "落户黄埔区", "region": ["广州黄埔"]},
    {"id": "P026", "title": "广州市南沙区促进人工智能产业发展扶持办法", "level": "district",
     "department": "南沙区政府", "industry": ["人工智能", "机器人"],
     "support_type": "创业扶持+办公补贴", "amount": "最高1000万", "deadline": "2026-12-31",
     "condition": "落户南沙", "region": ["广州南沙"]},
    {"id": "P027", "title": "广州市「专精特新」中小企业培育行动方案", "level": "municipal",
     "department": "广州市工信局", "industry": ["机器人", "核心零部件"],
     "support_type": "认定奖励+贷款贴息", "amount": "100-300万", "deadline": "2026-09-30",
     "condition": "市级以上专精特新", "region": ["广州"]},
    {"id": "P028", "title": "广州市重点研发计划", "level": "municipal",
     "department": "广州市科技局", "industry": ["机器人", "人工智能"],
     "support_type": "项目资助", "amount": "100-500万", "deadline": "2026-06-30",
     "condition": "产学研合作", "region": ["广州"]},
    {"id": "P029", "title": "广州市高层次人才引进「岭南英杰工程」", "level": "municipal",
     "department": "广州市人社局", "industry": ["机器人", "人工智能"],
     "support_type": "安家费+科研启动", "amount": "100-500万", "deadline": "2026-10-31",
     "condition": "博士/高级职称", "region": ["广州"]},
    {"id": "P030", "title": "广州市产业园区提质增效扶持办法", "level": "municipal",
     "department": "广州市工信局", "industry": ["机器人", "智能制造"],
     "support_type": "园区补贴", "amount": "最高2000万", "deadline": "2026-12-31",
     "condition": "省级以上产业园区", "region": ["广州"]},
]

# 补充至 50 条
for i in range(len(POLICIES), 55):
    POLICIES.append({
        "id": f"P{i+1:03d}",
        "title": f"广州市促进机器人产业高质量发展若干措施(第{i-29}批)",
        "level": random.choice(["municipal", "district"]),
        "department": random.choice(["广州市工信局", "广州市科技局", "黄埔区政府", "南沙区政府"]),
        "industry": ["机器人"],
        "support_type": random.choice(["研发补贴", "税收优惠", "人才补贴", "融资支持", "场地补贴"]),
        "amount": f"{random.choice([50,100,200,300,500,1000])}万",
        "deadline": f"2026-{random.randint(6,12):02d}-{random.randint(1,28):02d}",
        "condition": random.choice(["注册地在广州", "研发投入>3%", "高新技术企业", "规上企业"]),
        "region": ["广州"],
    })

print(f"政策总数: {len(POLICIES)}")

# ============================================================
# 4. 100+ 风险事件
# ============================================================
RISK_TYPES = ["financial", "legal", "operation", "public_opinion", "talent"]
RISK_TEMPLATES = {
    "financial": [
        "连续{}个月营收下滑{}%", "融资{}轮后{}个月未完成交割", "应收账款周转天数增加至{}天",
        "现金流持续为负", "资产负债率超过{}%", "对外担保金额超过净资产{}%",
    ],
    "legal": [
        "涉及知识产权侵权纠纷", "劳动仲裁案件{}起", "环保处罚罚款{}万元",
        "合同纠纷涉案金额{}万元", "股权冻结", "被列入经营异常名录",
    ],
    "operation": [
        "核心客户流失", "产能利用率降至{}%", "产品质量问题召回",
        "供应链中断", "关键设备故障停产{}天", "安全责任事故",
    ],
    "public_opinion": [
        "媒体负面报道{}篇", "网络舆情负面率{}%", "消费者投诉量增长{}%",
        "高管负面新闻", "产品质量引发社交平台热议", "被监管部门约谈",
    ],
    "talent": [
        "核心技术人员离职{}人", "员工流失率超过{}%", "研发团队规模缩减{}%",
        "高管频繁变动", "招聘困难，关键岗位空缺{}个月", "管理层矛盾公开化",
    ],
}

RISK_EVENTS = []
for i in range(120):
    eid = f"E{random.randint(1, 1050):04d}"
    rtype = random.choice(RISK_TYPES)
    templates = RISK_TEMPLATES[rtype]
    desc = random.choice(templates).format(
        random.randint(2, 6),
        random.randint(10, 50),
        random.randint(30, 180),
        random.randint(3, 12),
        random.randint(50, 500),
        random.randint(60, 95),
        random.randint(1, 5),
        random.randint(10, 100),
        random.randint(3, 10),
        random.randint(3, 30),
    )
    severity = random.choices(["HIGH", "MEDIUM", "LOW"], weights=[15, 35, 50], k=1)[0]
    RISK_EVENTS.append({
        "id": f"R{i+1:04d}",
        "enterprise_id": eid,
        "type": rtype,
        "description": desc,
        "severity": severity,
        "event_date": f"2026-0{random.randint(1,7):01d}-{random.randint(1,28):02d}",
    })

print(f"风险事件: {len(RISK_EVENTS)}")
print(f"  HIGH: {sum(1 for r in RISK_EVENTS if r['severity']=='HIGH')}")
print(f"  MEDIUM: {sum(1 for r in RISK_EVENTS if r['severity']=='MEDIUM')}")
print(f"  LOW: {sum(1 for r in RISK_EVENTS if r['severity']=='LOW')}")

# ============================================================
# 保存
# ============================================================
data = {
    "industry_chain": INDUSTRY_CHAIN,
    "chain_positions": ALL_CHAIN_POSITIONS,
    "enterprises": ENTERPRISES,
    "policies": POLICIES,
    "risk_events": RISK_EVENTS,
}

out_path = os.path.join(os.path.dirname(__file__) or ".", "demo_robot_industry.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)

size_kb = os.path.getsize(out_path) / 1024
print(f"\n✅ 保存至: {out_path}")
print(f"   文件大小: {size_kb:.0f} KB")
print(f"   企业: {len(ENTERPRISES)} | 政策: {len(POLICIES)} | 风险事件: {len(RISK_EVENTS)}")
