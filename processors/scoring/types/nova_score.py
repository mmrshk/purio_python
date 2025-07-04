class NovaScoreCalculator:
    def calculate(self, product_data):
        """Stub: Calculate NovaScore for a product. Returns a value between 0 and 100."""
        nova = product_data.get('nova_group')
        try:
            nova = int(nova)
            # Map 1 (best) to 100, 2 to 75, 3 to 50, 4 (worst) to 25
            score = 125 - nova * 25
            return max(0, min(100, score))
        except (TypeError, ValueError):
            return 50 