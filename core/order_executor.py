import logging

class OrderExecutor:
    def __init__(self, exchange_adapter):
        self.exchange = exchange_adapter
        self.logger = logging.getLogger("OrderExecutor")

    def place_market_order(self, symbol, side, amount):
        try:
            # Исправлено: create_market_order → place_market_order
            response = self.exchange.place_market_order(symbol, side, amount)
            self.logger.info(f"Market order {side} {amount} {symbol} executed: {response}")
            return {
                "avg_price": response.get("avg_price", 0),
                "filled_qty": response.get("filled_qty", amount),
                "amount": amount
            }
        except Exception as e:
            self.logger.error(f"Failed to execute market order: {e}")
            return {"avg_price": 0, "filled_qty": 0, "amount": 0}

    def place_limit_order(self, symbol, side, price, amount):
        try:
            response = self.exchange.place_limit_order(symbol, side, price, amount)
            self.logger.info(f"Limit order {side} {amount} {symbol} at {price} placed: {response}")
            return response
        except Exception as e:
            self.logger.error(f"Failed to place limit order: {e}")
            return {}