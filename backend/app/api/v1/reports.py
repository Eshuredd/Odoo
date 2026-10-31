from datetime import date
from fastapi import APIRouter
from app.api.commercial_dependencies import Operator, Database
from app.services.reports import summary
from app.schemas.financial import ReportSummary

router=APIRouter(prefix="/reports",tags=["reports"])


@router.get("/summary", response_model=ReportSummary)
def report(as_of:date, actor:Operator, db:Database, from_date:date|None=None, to_date:date|None=None):
    return summary(db,as_of,from_date,to_date)
