from decimal import Decimal, ROUND_DOWN
import decimal
import logging

logger = logging.getLogger(__name__)

class BinanceAdapter:
    # ... другие методы и инициализация ...

    def _get_symbol_lot_info(self, symbol):
        """Получить фильтры LOT_SIZE и PRICE_FILTER по инструменту"""
        if self.mode == "EMULATION":
            # Для эмуляции просто возвращаем тестовые значения
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
        """Округлить количество до допустимого диапазона и шага"""
        lot = self._get_symbol_lot_info(symbol)
        step = lot['stepSize']
        min_qty = lot['minQty']
        max_qty = lot['maxQty']
        # Округляем вниз к ближайшему шагу
        quantity = (Decimal(quantity) // step) * step
        quantity = quantity.quantize(step, rounding=decimal.ROUND_DOWN)
        # Граничные условия
        if quantity < min_qty:
            return Decimal('0')
        if quantity > max_qty:
            return max_qty
        return quantity

    def _round_price(self, symbol, price):
        """Округлить цену до допустимого tickSize и диапазона"""
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

            # Округляем количество ДЛЯ ВСЕХ типов ордеров
            quantity = self._round_quantity(symbol, quantity)
            if quantity == Decimal('0'):
                raise ValueError(f"QTY меньше минимального или некорректен для {symbol}")

            # Округление цены под PRICE_FILTER, если есть цена (для лимитных ордеров)
            if price is not None:
                price = self._round_price(symbol, price)

            if self.mode == "EMULATION":
                return self._create_test_order(symbol, side, order_type, quantity, price)
                
            params = {
                'symbol': symbol,
                'side': side,
                'type': order_type.upper(),
                'quantity': float(quantity)
            }
            if price and order_type.upper() == "LIMIT":
                params['price'] = float(price)
                params['timeInForce'] = 'GTC'
            
            if self.mode in ["TESTNET", "PRODUCTION"]:
                logger.info(f"Создание ордера: {params}")
                response = self.client.create_order(**params)
                return {
                    'id': response['orderId'],
                    'symbol': symbol,
                    'side': side,
                    'type': order_type,
                    'amount': Decimal(str(params['quantity'])),
                    'price': Decimal(str(params.get('price', response.get('fills', [{}])[0].get('price', 0)))),
                    'status': response['status'],
                    'filled_qty': Decimal(str(response.get('executedQty', 0))),
                    'avg_price': Decimal(str(response.get('fills', [{}])[0].get('price', 0)))
                }
                
        except Exception as e:
            logger.error(f"Ошибка создания ордера: {str(e)}")
            raise

    # ... остальные методы без изменений ...