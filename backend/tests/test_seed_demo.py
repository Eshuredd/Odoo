import pytest
from sqlalchemy import select,func
from app.db.session import create_db_engine,create_session_factory
from app.models import Invoice,Payment,Subscription,User
from scripts.seed_demo import main
from conftest import TEST_PASSWORD


def configure(monkeypatch,url):
    for key,value in {"DEMO_DATABASE_URL":url,"ADMIN_EMAIL":"synthetic-admin@example.com","ADMIN_PASSWORD":TEST_PASSWORD,
        "DEMO_STAFF_EMAIL":"synthetic-staff@example.com","DEMO_STAFF_PASSWORD":TEST_PASSWORD,"DEMO_CUSTOMER_PASSWORD":TEST_PASSWORD}.items():monkeypatch.setenv(key,value)


def test_demo_seed_calculated_records_and_repeat_safety(monkeypatch,database_url):
    configure(monkeypatch,database_url);main()
    engine=create_db_engine(database_url)
    try:
        with create_session_factory(engine)() as session:
            assert session.scalar(select(func.count()).select_from(Subscription))==9
            assert session.scalar(select(func.count()).select_from(Payment))==2
            assert session.scalar(select(func.count()).select_from(Invoice).where(Invoice.status=="paid"))==1
            users=[(user.id,user.password_hash) for user in session.scalars(select(User).order_by(User.id))]
            count=session.scalar(select(func.count()).select_from(Invoice))
        main()
        with create_session_factory(engine)() as session:
            assert session.scalar(select(func.count()).select_from(Invoice))==count
            assert [(user.id,user.password_hash) for user in session.scalars(select(User).order_by(User.id))]==users
    finally:engine.dispose()


def test_demo_refuses_existing_ordinary_data(monkeypatch,commerce):
    configure(monkeypatch,str(commerce.client.app.state.session_factory.kw["bind"].url))
    with pytest.raises(SystemExit,match="Refusing"):main()
