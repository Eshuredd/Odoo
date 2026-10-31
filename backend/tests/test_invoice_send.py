from sqlalchemy import select,func
from app.models import AuditLog,EmailOutbox
from app.services.mailer import MailDeliveryError
from test_payments import confirmed


def test_send_offline_content_audit_and_failure_rollback(commerce):
    c=commerce;invoice=confirmed(c)
    result=c.call("POST",f"/invoices/{invoice['id']}/send")
    assert result["delivery"]=="offline_outbox"
    with c.client.app.state.session_factory() as session:
        message=session.scalar(select(EmailOutbox))
        assert message.recipient_email=="buyer@example.com" and invoice["number"] in message.body
        assert str(invoice["period_start"]) in message.body and "INR 2057.60" in message.body
        assert session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action=="invoice.send_requested"))==1
    class Failing:
        def send(self,*args,**kwargs):raise MailDeliveryError("Synthetic failure")
    c.client.app.state.mailer=Failing()
    c.call("POST",f"/invoices/{invoice['id']}/send",503)
    with c.client.app.state.session_factory() as session:
        assert session.scalar(select(func.count()).select_from(AuditLog).where(AuditLog.action=="invoice.send_requested"))==1
