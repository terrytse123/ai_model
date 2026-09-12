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

HTML_WITH_GENERIC_PRICE = '''
<html>
  <body>
    <script type="application/ld+json">{"offers":{"price":"109.99"}}</script>
    <div>Price: $109.99</div>
  </body>
</html>
'''

HTML_WITH_PRICETOPAY = '''
<html>
  <body>
    <span id="apex-pricetopay-accessibility-label" data-pricetopay-label="{priceToPay}">$109.99</span>
    <span class="a-price priceToPay apex-pricetopay-value">
      <span class="a-offscreen"> </span>
      <span aria-hidden="true">
        <span class="a-price-symbol">$</span>
        <span class="a-price-whole">109<span class="a-price-decimal">.</span></span>
        <span class="a-price-fraction">99</span>
      </span>
    </span>
  </body>
</html>
'''

HTML_WITH_MISLEADING_GENERIC_PRICE = '''
<html>
  <body>
    <div>$10</div>
    <div class="a-price priceToPay apex-pricetopay-value">
      <span class="a-price-symbol">$</span>
      <span class="a-price-whole">109<span class="a-price-decimal">.</span></span>
      <span class="a-price-fraction">99</span>
    </div>
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


def test_item_history_filters_by_url():
    from amazon_price_monitor import get_history_for_url

    history = [
        {"url": "https://a.example/one", "checked_at": "2026-09-01 00:00:00", "price": "10.00"},
        {"url": "https://a.example/two", "checked_at": "2026-09-02 00:00:00", "price": "15.00"},
        {"url": "https://a.example/one", "checked_at": "2026-09-03 00:00:00", "price": "12.00"},
    ]

    assert len(get_history_for_url(history, "https://a.example/one")) == 2
    assert len(get_history_for_url(history, "https://a.example/two")) == 1


def test_extract_price_from_generic_price_string():
    from amazon_price_monitor import extract_price

    assert extract_price(HTML_WITH_GENERIC_PRICE) == Decimal('109.99')


def test_extract_price_from_price_to_pay_markup():
    from amazon_price_monitor import extract_price

    assert extract_price(HTML_WITH_PRICETOPAY) == Decimal('109.99')


def test_extract_price_prefers_buybox_over_earlier_generic_price():
    from amazon_price_monitor import extract_price

    assert extract_price(HTML_WITH_MISLEADING_GENERIC_PRICE) == Decimal('109.99')
