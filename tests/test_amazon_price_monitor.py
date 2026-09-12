from datetime import datetime, timedelta
from decimal import Decimal

from amazon_price_monitor import app, extract_price


HTML_WITH_META = '''
<html>
  <head>
    <meta property="og:price:amount" content="42.50" />
    <meta property="og:price:currency" content="USD" />
  </head>
  <body></body>
</html>
'''

HTML_WITH_A_PRICE = '''
<html>
  <body>
    <span id="priceblock_ourprice">$39.99</span>
  </body>
</html>
'''


def test_extract_price_from_meta_tag():
    assert extract_price(HTML_WITH_META) == Decimal('42.50')


def test_extract_price_from_buybox_span():
    assert extract_price(HTML_WITH_A_PRICE) == Decimal('39.99')


def test_web_app_check_route():
    client = app.test_client()
    response = client.get('/health')
    assert response.status_code == 200
    assert response.get_json()['status'] == 'ok'


def test_price_history_filters_by_days():
    from amazon_price_monitor import get_history_for_days

    now = datetime.now()
    history = [
        {"checked_at": (now - timedelta(days=100)).strftime("%Y-%m-%d %H:%M:%S"), "price": "10.00"},
        {"checked_at": (now - timedelta(days=40)).strftime("%Y-%m-%d %H:%M:%S"), "price": "15.00"},
        {"checked_at": (now - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S"), "price": "20.00"},
    ]
    recent_30 = get_history_for_days(history, 30)
    recent_60 = get_history_for_days(history, 60)
    recent_90 = get_history_for_days(history, 90)

    assert len(recent_30) == 1
    assert len(recent_60) == 2
    assert len(recent_90) == 2
