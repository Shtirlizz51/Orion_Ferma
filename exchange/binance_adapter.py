from decimal import Decimal
import decimal

class BinanceAdapter:
    def __init__(self, mode, api_key=None, api_secret=None):
        self.mode = mode
        self.api_key = api_key
        self.api_secret = api_secret
        self.client = None  # Здесь можно инициализировать клиента Binance при необходимости

    def _get_symbol_lot_info(self, symbol):
        """
        Получить фильтры LOT_SIZE и PRICE_FILTER по инструменту
        """
        if self.mode == "EMULATION":
            # Для эмуляции возвращаем тестовые значения
            return {
                'minQty': Decimal('0.00001'),
                'maxQty': Decimal('10000'),
                'stepSize': Decimal('0.00001'),
                'minPrice': Decimal('1.0'),
                'maxPrice': Decimal('1000000'),
                'tickSize': Decimal('0.01')
            }
        info = self.client.get_symbol_info(symbol.upper())
        filters = {f['filterType']: f for f in info['filters']}
        lot = filters['LOT_SIZE']
        price = filters['PRICE_FILTER']
        return {
            'minQty': Decimal(lot['minQty']),
            'maxQty': Decimal(lot['maxQty']),
            'stepSize': Decimal(lot['stepSize']),
            'minPrice': Decimal(price['minPrice']),
            'maxPrice': Decimal(price['maxPrice']),
            'tickSize': Decimal(price['tickSize'])
        }

    def _round_quantity(self, symbol, quantity):
        """
        Округлить количество до допустимого диапазона и шага
        """
        lot = self._get_symbol_lot_info(symbol)
        step = lot['stepSize']
        min_qty = lot['minQty']
        max_qty = lot['maxQty']
        quantity = (Decimal(quantity) // step) * step
        quantity = quantity.quantize(step, rounding=decimal.ROUND_DOWN)
        if quantity < min_qty:
            return Decimal('0')
        if quantity > max_qty:
            return max_qty
        return quantity

    def _round_price(self, symbol, price):
        """
        Округлить цену до допустимого tickSize и диапазона
        """
        lot = self._get_symbol_lot_info(symbol)
        tick = lot.get('tickSize', Decimal('0.01'))
        min_price = lot.get('minPrice', Decimal('0.01'))
        max_price = lot.get('maxPrice', Decimal('1000000'))
        price = (Decimal(price) // tick) * tick
        price = price.quantize(tick, rounding=decimal.ROUND_DOWN)
        if price < min_price:
            return min_price
        if price > max_price:
            return max_price
        return price

    def create_order(self, symbol: str, side: str, order_type: str, 
                   quantity: Decimal, price: Decimal = None, quote_amount: bool = False) -> dict:
        try:
            symbol = symbol.upper()
            side = side.upper()
            quantity = self._round_quantity(symbol, quantity)
            if quantity == Decimal('0'):
                raise ValueError(f"QTY меньше минимального или некорректен для {symbol}")
            if price is not None:
                price = self._round_price(symbol, price)

            if self.mode == "EMULATION":
                # Логика эмуляции
                pass
            else:
                # Логика реальных ордеров
                pass

        except Exception as e:
            raise e

    def check_connection(self):
        """
        Проверка соединения с биржей
        """
        if self.mode == "EMULATION":
            return True
        # Здесь можно добавить реальную проверку соединения через self.client
        return True