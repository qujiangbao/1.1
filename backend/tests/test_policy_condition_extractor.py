from app.services.policy_condition_extractor import extract_policy_condition_drafts


def test_extracts_only_explicit_source_backed_drafts():
    content = (
        "申报单位应在广州市依法注册登记并具有独立法人资格。"
        "企业注册资本不低于500万元，拥有发明专利不少于5项。"
        "企业发展前景良好。"
    )

    rules = extract_policy_condition_drafts(content)

    assert {rule["field"] for rule in rules} == {"region", "capital_amount", "patents_count"}
    assert all(rule["review_status"] == "DRAFT" for rule in rules)
    assert all(rule["source_text"] in content for rule in rules)
    capital = next(rule for rule in rules if rule["field"] == "capital_amount")
    assert capital["expected_value"] == 500


def test_does_not_invent_rules_from_general_policy_language():
    rules = extract_policy_condition_drafts(
        "本政策支持机器人与人工智能产业高质量发展，鼓励企业加强研发创新。"
    )

    assert rules == []


def test_extracts_explicit_policy_enterprise_definition_as_industry_draft():
    source = (
        "本政策措施所称的具身智能机器人企业是指从事具身智能机器人整机、"
        "核心零部件生产和系统集成等经营活动的相关企业。"
    )

    rules = extract_policy_condition_drafts(source)

    assert len(rules) == 1
    assert rules[0]["field"] == "industry"
    assert rules[0]["expected_value"] == ["具身智能机器人", "机器人整机", "核心零部件", "系统集成"]
    assert rules[0]["source_text"] == source
