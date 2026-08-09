import pytest
from pydantic import ValidationError

from app.api.v1.service_tickets import TicketCreate, TicketUpdate


def test_service_ticket_requires_real_business_content():
    ticket = TicketCreate(
        enterprise_name="广州测试机器人有限公司",
        subject="政策申报材料核验",
        description="请协助核验申报材料清单和截止时间",
        category="政策申报",
        priority="HIGH",
    )
    assert ticket.subject == "政策申报材料核验"


def test_resolving_ticket_requires_resolution():
    with pytest.raises(ValidationError, match="处理结果"):
        TicketUpdate(status="RESOLVED")
    assert TicketUpdate(status="RESOLVED", resolution="材料清单已复核并交付企业").status == "RESOLVED"
